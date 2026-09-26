"""The reliability loop -- drives one incident through its lifecycle, and knows when to stop.

    detect -> investigate -> diagnose -> assess risk -> [approval] -> remediate -> verify
                  ^                                                                |
                  +---------------- re-investigate (attempt + 1, capped) <---------+

`ReliabilityLoop.advance` performs the next automated step, repeatedly, until it reaches a
point that needs a human, a terminal state, or its own step budget. It never loops on its
own: a caller drives it (an API call, the evaluation harness, the demo script).

TERMINATION (ERRATA A4) is structural, not hoped-for:
  * every pass through REINVESTIGATING bumps `attempt`; at BRE_MAX_ATTEMPTS the incident goes
    to ABANDONED (verification failed) or FAILED (remediation could not even be applied);
  * each `advance` call has a step budget, so no request can spin;
  * the only waiting state is AWAITING_APPROVAL, and waiting is not a step.

LEDGER HYGIENE across attempts: predictions from an attempt that failed *verification* are
closed `refuted` by the verifier (a real negative result). Predictions from an attempt that
never reached verification -- the executor errored, changed nothing, or tripped the diff
guard -- are closed `abandoned`, not refuted: nothing tested them, so no reputation moves.
Without that, a later attempt's pass would retroactively "confirm" an earlier, untested guess.

Every state change goes through `Lifecycle.transition`, so the approval gate cannot be
skipped by this driver either.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from apps.api.database import (
    ApprovalDB, DiagnosisDB, EvidenceDB, IncidentDB, InvestigationDB,
    RemediationDB, RiskAssessmentDB, VerificationDB,
)
from apps.api.services import investigation_service
from apps.api.services.risk_service import assess_risk
from asmos_bridge.consolidation.learner import consolidate
from asmos_bridge.memory.store import MemoryNotVerified
from bob.adapter import BobAdapter
from bob.errors import BobError, BobNotAvailable
from models.diagnosis import Diagnosis
from models.incident import IncidentStatus
from reliability.ledger.record import OutcomeLedger
from reliability.orchestration import gate
from reliability.orchestration.lifecycle import Lifecycle, incident_view, latest_evidence
from reliability.remediation.allowlist import RepoAllowlist, RepositoryNotAllowed
from reliability.remediation.engine import RemediationEngine, RemediationRefused
from reliability.remediation.executors import Executor, select_executor
from reliability.remediation.git_ops import DirtyWorktree, GitError
from reliability.risk.policies import ApprovalPolicy, Requirement
from reliability.verification.test_runner import TestRunner
from reliability.verification.verifier import Verifier, max_attempts

logger = logging.getLogger("bre.loop")

LOOP_ID = "reliability-loop"
S = IncidentStatus
TERMINAL = {S.RESOLVED, S.CLOSED, S.FAILED, S.ABANDONED}


@dataclass
class Step:
    action: str
    from_status: str
    to_status: str
    note: str = ""
    data: dict = field(default_factory=dict)


@dataclass
class AdvanceResult:
    incident_id: str
    status: str
    steps: list[Step] = field(default_factory=list)
    blocked_on: Optional[str] = None   # approval | allowlist | dirty_worktree | bob_unavailable | error | budget | terminal
    message: Optional[str] = None


@dataclass
class DiagnoseRequest:
    db: Session
    incident: IncidentDB
    evidence: list[dict]
    root: str
    attempt: int
    prior_attempts: list[dict]
    topic: str


@dataclass
class DiagnoseResult:
    diagnosis: Diagnosis
    source: str                 # which diagnosis source produced it (S8 routes between sources)
    meta: dict = field(default_factory=dict)


def bob_diagnoser(req: DiagnoseRequest) -> DiagnoseResult:
    """The default diagnosis source: IBM Bob (or its replay stand-in, when explicitly enabled)."""
    adapter = BobAdapter(req.db, topic=req.topic)
    diagnosis = adapter.investigate(
        incident_view(req.incident), req.evidence, working_directory=req.root,
        attempt=req.attempt, prior_attempts=req.prior_attempts,
    )
    return DiagnoseResult(diagnosis, "bob", {})


def _evidence_dicts(rows) -> list[dict]:
    return [{"source_type": e.source_type, "source_reference": e.source_reference, "content": e.content,
             "relevance_score": e.relevance_score, "confidence": e.confidence} for e in rows]


def infer_topic(incident: IncidentDB) -> str:
    topic = (incident.metadata_json or {}).get("topic")
    return str(topic) if topic else "general"


class ReliabilityLoop:
    def __init__(
        self,
        db: Session,
        *,
        diagnoser: Callable[[DiagnoseRequest], DiagnoseResult] = bob_diagnoser,
        executor_factory: Callable[[], Executor] = select_executor,
        allowlist: Optional[RepoAllowlist] = None,
        runner: Optional[TestRunner] = None,
    ) -> None:
        self.db = db
        self.diagnoser = diagnoser
        self.executor_factory = executor_factory
        self.allowlist = allowlist if allowlist is not None else RepoAllowlist.from_env()
        self.runner = runner or TestRunner()
        self.lifecycle = Lifecycle(db)

    # ── public ───────────────────────────────────────────────────────────────────────

    def advance(self, incident_id: str, *, repo_path: Optional[str] = None, max_steps: int = 12) -> AdvanceResult:
        row = self.db.get(IncidentDB, incident_id)
        if row is None:
            raise KeyError(f"incident not found: {incident_id}")
        result = AdvanceResult(incident_id, row.status)

        for _ in range(max_steps):
            status = S(row.status)
            if status in TERMINAL:
                result.blocked_on, result.message = "terminal", f"incident is {status.value}"
                break
            try:
                step = self._step(row, status, repo_path)
            except _Blocked as blocked:
                result.blocked_on, result.message = blocked.kind, str(blocked)
                break
            self.db.commit()
            result.steps.append(step)
            result.status = row.status
        else:
            result.blocked_on, result.message = "budget", f"stopped after {max_steps} steps; call advance again to continue"

        if result.blocked_on == "budget" and S(row.status) in TERMINAL:
            result.blocked_on, result.message = "terminal", f"incident is {row.status}"
        result.status = row.status
        self.db.commit()
        return result

    # ── one step ─────────────────────────────────────────────────────────────────────

    def _step(self, row: IncidentDB, status: IncidentStatus, repo_path: Optional[str]) -> Step:
        before = status.value
        if status in (S.DETECTED, S.REINVESTIGATING):
            return self._investigate(row, before, repo_path)
        if status is S.INVESTIGATING:
            return self._diagnose(row, before, repo_path)
        if status is S.DIAGNOSED:
            return self._assess(row, before)
        if status is S.RISK_ASSESSED:
            return self._route_after_risk(row, before)
        if status is S.AWAITING_APPROVAL:
            return self._check_approval(row, before)
        if status is S.REMEDIATING:
            return self._remediate(row, before, repo_path)
        if status is S.VERIFYING:
            return self._verify(row, before)
        raise _Blocked("error", f"no step defined for {status.value}")

    def _root(self, row: IncidentDB, repo_path: Optional[str]) -> str:
        try:
            return investigation_service.resolve_repo_root(
                investigation_service._to_incident_model(row), override=repo_path)
        except investigation_service.RepoRootUnavailable as exc:
            raise _Blocked("error", str(exc)) from exc

    def _investigate(self, row, before, repo_path) -> Step:
        root = self._root(row, repo_path)
        try:
            inv, evidence, _ = investigation_service.run_investigation(self.db, row, repo_path=root)
        except ValueError as exc:
            raise _Blocked("error", str(exc)) from exc
        return Step("investigate", before, row.status,
                    f"{len(evidence)} evidence items across {len({e.source_type for e in evidence})} source types",
                    {"investigation_id": inv.id, "attempt": row.attempt or 1})

    def _latest_evidence(self, row) -> list[dict]:
        return latest_evidence(self.db, row.id)

    def _prior_attempts(self, row) -> list[dict]:
        prior = []
        rolled = (self.db.query(RemediationDB)
                  .filter(RemediationDB.incident_id == row.id, RemediationDB.status.in_(("rolled_back", "failed")))
                  .order_by(RemediationDB.created_at).all())
        for rem in rolled:
            why = rem.summary if rem.status == "failed" else "verification failed"
            ver = (self.db.query(VerificationDB).filter(VerificationDB.remediation_id == rem.id)
                   .order_by(VerificationDB.created_at.desc()).first())
            if ver and isinstance(ver.levels, dict):
                why = (ver.levels.get("verdict") or {}).get("reason") or why
            prior.append({"attempt": rem.attempt, "summary": rem.summary, "why_failed": why})
        return prior

    def _diagnose(self, row, before, repo_path) -> Step:
        root = self._root(row, repo_path)
        evidence = self._latest_evidence(row)
        topic = infer_topic(row)
        try:
            res = self.diagnoser(DiagnoseRequest(
                self.db, row, evidence, root, row.attempt or 1, self._prior_attempts(row), topic))
        except BobNotAvailable as exc:
            raise _Blocked("bob_unavailable", str(exc)) from exc
        except BobError as exc:
            raise _Blocked("error", f"diagnosis failed ({type(exc).__name__}): {exc}") from exc

        d = res.diagnosis
        self.db.add(DiagnosisDB(
            id=d.id, incident_id=row.id, root_cause=d.root_cause, confidence=d.confidence,
            affected_components=d.affected_components, evidence_ids=d.evidence_ids,
            assumptions=d.assumptions, unresolved_uncertainty=d.unresolved_uncertainty,
        ))
        self.lifecycle.record(row.id, "diagnosis", actor=res.source,
                              detail={"diagnosis_id": d.id, "confidence": d.confidence, "topic": topic,
                                      "attempt": row.attempt or 1, **res.meta})
        self.lifecycle.transition(row, S.DIAGNOSED, actor=res.source, detail={"diagnosis_id": d.id})
        return Step("diagnose", before, row.status, d.root_cause[:160],
                    {"diagnosis_id": d.id, "confidence": d.confidence, "source": res.source})

    def _latest_diagnosis(self, row) -> DiagnosisDB:
        d = (self.db.query(DiagnosisDB).filter(DiagnosisDB.incident_id == row.id)
             .order_by(DiagnosisDB.created_at.desc(), DiagnosisDB.id.desc()).first())
        if d is None:
            raise _Blocked("error", "no diagnosis on record")
        return d

    def _assess(self, row, before) -> Step:
        d = self._latest_diagnosis(row)
        evidence = self._latest_evidence(row)
        comps = list(d.affected_components or [])
        risk = assess_risk(
            self.db, row,
            blast_radius=len(comps),
            database_migration=any("migration" in c.lower() for c in comps),
            api_surface_affected=any(re.search(r"(^|/)(api|routes?|openapi)(/|$)", c.lower()) for c in comps),
            tests_available="partial" if any(e["source_type"] == "test" for e in evidence) else "none",
            affected_components=comps,
            diagnosis_confidence=d.confidence, diagnosis_root_cause=d.root_cause,
            topic=infer_topic(row),
        )
        self.lifecycle.transition(row, S.RISK_ASSESSED, actor=LOOP_ID, detail={"risk_id": risk.id})
        return Step("assess_risk", before, row.status, f"{risk.risk_level} (score {risk.factors.get('score')})",
                    {"risk_id": risk.id, "level": risk.risk_level, "factors": risk.factors})

    def _route_after_risk(self, row, before) -> Step:
        level = gate.latest_risk_level(self.db, row.id) or "CRITICAL"
        if ApprovalPolicy().required_for(level) is Requirement.AUTO:
            self.lifecycle.transition(row, S.REMEDIATING, actor=LOOP_ID, detail={"approval": "not required (LOW)"})
            return Step("proceed", before, row.status, f"{level}: no approval required")
        self.lifecycle.transition(row, S.AWAITING_APPROVAL, actor=LOOP_ID, detail={"level": level})
        return Step("request_approval", before, row.status, f"{level}: a human must approve before any change is made")

    def _check_approval(self, row, before) -> Step:
        level = gate.latest_risk_level(self.db, row.id) or "CRITICAL"
        assessment = (self.db.query(RiskAssessmentDB).filter(RiskAssessmentDB.incident_id == row.id)
                      .order_by(RiskAssessmentDB.created_at.desc()).first())
        latest = None
        if assessment is not None:
            latest = (self.db.query(ApprovalDB)
                      .filter(ApprovalDB.incident_id == row.id, ApprovalDB.operator_id.isnot(None),
                              ApprovalDB.created_at >= assessment.created_at)
                      .order_by(ApprovalDB.created_at.desc(), ApprovalDB.id.desc()).first())
        if latest is not None and latest.decision == "REJECTED":
            self.lifecycle.transition(row, S.CLOSED, actor=latest.operator_name or LOOP_ID,
                                      detail={"reason": latest.reason, "rejected_by": latest.operator_name})
            OutcomeLedger(self.db).abandon_pending(row.id, closed_by=LOOP_ID)
            return Step("rejected", before, row.status, f"rejected by {latest.operator_name}: {latest.reason or 'no reason given'}")
        if gate.qualifying_approval(self.db, row.id, level) is None:
            raise _Blocked("approval", f"{level} risk: waiting for an authenticated operator to approve")
        self.lifecycle.transition(row, S.REMEDIATING, actor=latest.operator_name if latest else LOOP_ID,
                                  detail={"approved_by": latest.operator_name if latest else None})
        return Step("approved", before, row.status, f"approved by {latest.operator_name}")

    def _fail_attempt(self, row, before, why: str) -> Step:
        """A remediation that never reached verification. Untested predictions are ABANDONED."""
        OutcomeLedger(self.db).abandon_pending(row.id, closed_by=LOOP_ID)
        if (row.attempt or 1) < max_attempts():
            self.lifecycle.bump_attempt(row)
            target = S.REINVESTIGATING
        else:
            target = S.FAILED
        self.lifecycle.transition(row, target, actor=LOOP_ID, detail={"reason": why, "attempt": row.attempt})
        return Step("remediation_failed", before, row.status, why[:200], {"attempt": row.attempt})

    def _remediate(self, row, before, repo_path) -> Step:
        root = self._root(row, repo_path)
        try:
            executor = self.executor_factory()
        except BobNotAvailable as exc:
            raise _Blocked("bob_unavailable", str(exc)) from exc
        d = self._latest_diagnosis(row)
        engine = RemediationEngine(self.db, executor=executor, allowlist=self.allowlist, runner=self.runner)
        try:
            res = engine.run(row, repo_root=root, diagnosis={
                "root_cause": d.root_cause, "confidence": d.confidence,
                "affected_components": d.affected_components, "assumptions": d.assumptions,
            }, evidence=self._latest_evidence(row), topic=infer_topic(row))
        except RepositoryNotAllowed as exc:
            raise _Blocked("allowlist", str(exc)) from exc
        except DirtyWorktree as exc:
            raise _Blocked("dirty_worktree", str(exc)) from exc
        except (RemediationRefused, gate.GateViolation, GitError) as exc:
            raise _Blocked("error", f"{type(exc).__name__}: {exc}") from exc

        if not res.ok:
            return self._fail_attempt(row, before, res.reason or "remediation failed")
        self.lifecycle.transition(row, S.VERIFYING, actor=LOOP_ID, detail={"remediation_id": res.remediation.id})
        return Step("remediate", before, row.status,
                    f"patch on {res.remediation.patch_reference}: {', '.join(res.remediation.changed_files)}",
                    {"remediation_id": res.remediation.id, "branch": res.remediation.patch_reference,
                     "files": res.remediation.changed_files, "tokens": res.remediation.cost_tokens})

    def _verify(self, row, before) -> Step:
        rem = (self.db.query(RemediationDB)
               .filter(RemediationDB.incident_id == row.id, RemediationDB.status == "completed")
               .order_by(RemediationDB.created_at.desc(), RemediationDB.id.desc()).first())
        if rem is None:
            raise _Blocked("error", "VERIFYING but no completed remediation exists")
        hints = [row.description, row.metadata_json or {}]
        hints += [f"{e['source_reference']} {e['content']}" for e in self._latest_evidence(row)]
        try:
            res = Verifier(self.db, runner=self.runner).verify(row, rem, test_hints=hints)
        except (ValueError, GitError) as exc:
            raise _Blocked("error", f"{type(exc).__name__}: {exc}") from exc
        note = ("verified: " + ", ".join(res.fixed)) if res.passed else (res.reason or "verification failed")
        data = {"verification_id": res.verification.id, "passed": res.passed,
                "levels": {k: v.get("ok") for k, v in res.levels.items() if k != "verdict"}}
        if res.passed:
            # Only a passed verification promotes anything into memory (and the store re-checks it).
            try:
                memory = consolidate(self.db, row, res.verification)
            except MemoryNotVerified as exc:  # pragma: no cover - defence in depth
                logger.warning("consolidation refused for %s: %s", row.id, exc)
                memory = None
            if memory is not None:
                data["memory_id"] = memory.id
                self.lifecycle.record(row.id, "memory", actor="consolidation",
                                      detail={"memory_id": memory.id, "topic": memory.topic})
        return Step("verify", before, row.status, note, data)


class _Blocked(Exception):
    """The loop cannot proceed without something outside its control. Not a failure."""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind
