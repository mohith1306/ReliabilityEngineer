"""The remediation engine -- the write path, behind every gate. Stage S6.

`RemediationEngine.run` is the only function in BRE that changes a target repository. Its
ordering is the safety argument, so the order is part of the contract:

  1  incident must be REMEDIATING                    (state machine)
  2  approval gate re-checked                        (defence in depth: the transition into
                                                      REMEDIATING already required it, but a row
                                                      edited by hand must not walk around it)
  3  repository must be on the write allowlist       (deny by default)
  4  git CHECKPOINT + fresh bre/* branch             (refuses a dirty tracked tree)
  5  baseline test run, on the branch, BEFORE the patch
                                                     (so verification can tell "still broken"
                                                      from "newly broken")
  6  executor applies the change                     (Bob Shell agent mode, or replay)
  7  commit on the bre/* branch                      (BRE owns the commit, not the agent)
  8  DIFF GUARD: no deleted/skipped/vacuous tests    (a prompt is a request, a guard is a control)
  9  record changed files FROM GIT, cost, and open a `remediation_plan` prediction

Steps 1-4 raise before any side effect. From step 4 onward every failure path rolls back:
after `run` returns, the target repo is either on a bre/* branch holding a verified-to-be-
safe patch, or exactly where it started. It is never left half-written.

The engine does not verify (S7) and does not move the incident to VERIFYING: it reports.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session

from apps.api.database import RemediationDB
from bob.prompts import remediate_prompt
from models.incident import IncidentStatus
from reliability.ledger.record import open_remediation_prediction
from reliability.orchestration import gate
from reliability.orchestration.lifecycle import Lifecycle
from reliability.remediation import git_ops, guards
from reliability.remediation.allowlist import RepoAllowlist
from reliability.remediation.executors import Executor
from reliability.verification.test_runner import RunResult, Scope, TestRunner

logger = logging.getLogger("bre.remediation")

PREDICTOR_ID = "remediation-engine"


class RemediationRefused(RuntimeError):
    """A precondition failed before anything was changed."""


class GuardViolation(RuntimeError):
    def __init__(self, violations: list[guards.Violation]) -> None:
        self.violations = violations
        super().__init__("diff guard: " + "; ".join(str(v) for v in violations))


class NoChanges(RuntimeError):
    pass


@dataclass
class RemediationResult:
    remediation: RemediationDB
    ok: bool
    reason: Optional[str] = None
    baseline: Optional[RunResult] = None
    guard_violations: list[guards.Violation] = field(default_factory=list)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _as_dict(value: Any) -> dict:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return dict(value) if isinstance(value, dict) else {}


class RemediationEngine:
    def __init__(
        self,
        db: Session,
        *,
        executor: Executor,
        allowlist: Optional[RepoAllowlist] = None,
        runner: Optional[TestRunner] = None,
    ) -> None:
        self.db = db
        self.executor = executor
        self.allowlist = allowlist if allowlist is not None else RepoAllowlist.from_env()
        self.runner = runner or TestRunner()

    def run(
        self,
        incident,                     # IncidentDB row, status REMEDIATING
        *,
        repo_root: str,
        diagnosis: Any,               # Diagnosis or dict
        evidence: Iterable[Any] = (),
        topic: str = "general",
    ) -> RemediationResult:
        lifecycle = Lifecycle(self.db)

        # 1-3: refuse before touching anything
        if incident.status != IncidentStatus.REMEDIATING.value:
            raise RemediationRefused(
                f"incident {incident.id} is {incident.status}; remediation runs only in REMEDIATING"
            )
        gate.assert_can_enter(self.db, incident.id, IncidentStatus.REMEDIATING)
        root = str(self.allowlist.assert_writable(repo_root))

        # 4: checkpoint (may raise DirtyWorktree/GitError -- still before any change)
        attempt = incident.attempt or 1
        cp = git_ops.create_checkpoint(root, incident.id, attempt)
        row = RemediationDB(
            id=uuid.uuid4().hex[:12],
            incident_id=incident.id,
            status="in_progress",
            summary="",
            patch_reference=cp.branch,
            repo_root=root,
            base_branch=cp.base_branch,
            checkpoint_sha=cp.base_sha,
            executor=self.executor.name,
            attempt=attempt,
            preexisting_untracked=sorted(cp.preexisting_untracked),
            changed_files=[],
            tests_added=[],
            created_at=_now(),
        )
        self.db.add(row)
        self.db.flush()
        lifecycle.record(
            incident.id, "remediation", actor=PREDICTOR_ID,
            detail={"phase": "checkpoint", "branch": cp.branch, "base_sha": cp.base_sha,
                    "base_branch": cp.base_branch, "executor": self.executor.name},
        )

        baseline: Optional[RunResult] = None
        try:
            # 5: what is already red, before we touch anything
            baseline = self.runner.run(root, Scope.REGRESSION)
            row.baseline_failures = sorted(baseline.failing)

            # 6: the change
            prompt = remediate_prompt(_incident_view(incident), _as_dict(diagnosis), evidence)
            result = self.executor.apply(prompt, repo_root=root)

            # 7: BRE owns the commit
            changed_now = git_ops.working_changes(cp)
            if not changed_now:
                raise NoChanges("the executor finished but changed no files")
            commit = git_ops.commit_changes(
                cp,
                f"bre: remediation for incident {incident.id} (attempt {attempt})\n\n"
                f"{result.summary[:600]}\n\nexecutor: {self.executor.name}"
                + ("  [SIMULATED - not IBM Bob]" if result.simulated else ""),
            )

            # 8: the diff guard
            violations = guards.check_patch(git_ops.patch_diff(cp))
            if violations:
                raise GuardViolation(violations)

            # 9: record what git says happened
            files = git_ops.changed_files(cp)
            row.changed_files = files
            row.tests_added = git_ops.files_touching_tests(git_ops.added_files(cp))
            row.commit_sha = commit
            row.summary = result.summary[:2000]
            row.cost_tokens = result.tokens
            row.cost_wall_ms = result.wall_ms
            row.status = "completed"
            row.completed_at = _now()

            diag = _as_dict(diagnosis)
            open_remediation_prediction(
                self.db,
                incident_id=incident.id,
                predictor_id=result.provider,
                topic=topic,
                summary=result.summary[:500],
                changed_files=files,
                confidence=float(diag.get("confidence") or 0.5),
                components={
                    "executor": self.executor.name,
                    "provider": result.provider,
                    "simulated": result.simulated,
                    "changed_files": len(files),
                    "baseline_failures": len(baseline.failing),
                    "branch": cp.branch,
                    "checkpoint_sha": cp.base_sha,
                    "diagnosis_confidence": diag.get("confidence"),
                },
                attempt_number=attempt,
                cost_tokens=result.tokens,
                cost_wall_ms=result.wall_ms,
            )
            lifecycle.record(
                incident.id, "remediation", actor=result.provider,
                detail={"phase": "patched", "files": files, "commit": commit,
                        "tokens": result.tokens, "simulated": result.simulated},
            )
            return RemediationResult(row, ok=True, baseline=baseline)

        except Exception as exc:  # noqa: BLE001 -- every failure past the checkpoint must roll back
            reason = f"{type(exc).__name__}: {exc}"
            violations = list(exc.violations) if isinstance(exc, GuardViolation) else []
            self._abort(cp, row, reason, incident.id, lifecycle)
            logger.warning("remediation of %s rolled back: %s", incident.id, reason)
            return RemediationResult(row, ok=False, reason=reason, baseline=baseline,
                                     guard_violations=violations)

    # ── rollback path ─────────────────────────────────────────────────────────

    def _abort(self, cp: git_ops.Checkpoint, row: RemediationDB, reason: str,
               incident_id: str, lifecycle: Lifecycle) -> None:
        keep = f"{git_ops.slug(incident_id)}-attempt-{row.attempt or 1}"
        rollback_error = None
        try:
            git_ops.rollback(cp, keep_as=keep)
        except Exception as exc:  # noqa: BLE001
            rollback_error = f"{type(exc).__name__}: {exc}"
        row.status = "failed"
        row.summary = (row.summary or "") or reason[:2000]
        row.completed_at = _now()
        row.rolled_back_at = _now()
        lifecycle.record(
            incident_id, "remediation", actor=PREDICTOR_ID,
            detail={"phase": "rolled_back", "reason": reason,
                    **({"rollback_error": rollback_error} if rollback_error else {}),
                    "kept_failed_patch_as": f"refs/bre/failed/{keep}"},
        )
        if rollback_error:
            # The one outcome this engine must never hide: the target repo may be off-branch.
            raise RuntimeError(f"ROLLBACK FAILED for {cp.root}: {rollback_error}")


def _incident_view(incident) -> dict:
    return {
        "id": incident.id, "repository": incident.repository, "type": incident.type,
        "severity": incident.severity, "description": incident.description,
        "metadata": incident.metadata_json or {},
    }
