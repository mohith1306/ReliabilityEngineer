"""The reliability loop over HTTP: advance an incident, and read everything about it in one call.

`POST /{id}/advance` runs the loop until it needs a human, is terminal, or exhausts its step budget.
It changes incident state only through `Lifecycle.transition`, so the approval gate applies here exactly
as it does to `POST /{id}/transition`. Nothing in this module can write to a target repository except
by way of `ReliabilityLoop`, which routes through `RemediationEngine` (gate, allowlist, checkpoint, branch).
"""

from __future__ import annotations

import threading
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from apps.api import settings
from apps.api.database import (
    ApprovalDB, DiagnosisDB, EvidenceDB, IncidentDB, IncidentEventDB, InvestigationDB, OutcomeRecordDB,
    RemediationDB, RiskAssessmentDB, VerificationDB, get_db,
)
from bob.errors import BobError
from reliability.orchestration import gate
from reliability.orchestration.lifecycle import Lifecycle, to_model
from reliability.orchestration.loop import ReliabilityLoop
from reliability.orchestration.routed import routed_diagnoser
from reliability.remediation import git_ops
from reliability.remediation.executors import select_executor
from reliability.risk.policies import ApprovalPolicy, Requirement

router = APIRouter()
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


class AdvanceRequest(BaseModel):
    repo_path: Optional[str] = Field(default=None, description="Filesystem root of the target repository.")
    max_steps: int = Field(default=12, ge=1, le=30)


def _lock(incident_id: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(incident_id, threading.Lock())


def _iso(dt) -> Optional[str]:
    return dt.isoformat() if dt else None


@router.post("/{incident_id}/advance")
def advance(incident_id: str, body: AdvanceRequest | None = None, db: Session = Depends(get_db)):
    if db.get(IncidentDB, incident_id) is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    lock = _lock(incident_id)
    if not lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="this incident is already being advanced")
    try:
        req = body or AdvanceRequest()
        loop = ReliabilityLoop(db, diagnoser=routed_diagnoser, executor_factory=select_executor,
                               allowlist=settings.allowlist())
        res = loop.advance(incident_id, repo_path=req.repo_path, max_steps=req.max_steps)
    except BobError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    finally:
        lock.release()
    return {
        "incident_id": res.incident_id, "status": res.status, "blocked_on": res.blocked_on, "message": res.message,
        "steps": [{"action": s.action, "from": s.from_status, "to": s.to_status, "note": s.note, "data": s.data}
                  for s in res.steps],
    }


@router.get("/{incident_id}/timeline")
def timeline(incident_id: str, db: Session = Depends(get_db)):
    if db.get(IncidentDB, incident_id) is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return [_event(e) for e in Lifecycle(db).timeline(incident_id)]


def _event(e: IncidentEventDB) -> dict:
    return {"id": e.id, "kind": e.kind, "actor": e.actor, "from": e.from_status, "to": e.to_status,
            "detail": e.detail or {}, "at": _iso(e.created_at)}


@router.get("/{incident_id}/detail")
def detail(incident_id: str, db: Session = Depends(get_db)):
    """Everything the dashboard needs about one incident, in one round trip."""
    row = db.get(IncidentDB, incident_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    inv = (db.query(InvestigationDB).filter_by(incident_id=incident_id)
           .order_by(InvestigationDB.created_at.desc(), InvestigationDB.id.desc()).first())
    evidence = []
    if inv:
        evidence = [{"source_type": e.source_type, "reference": e.source_reference, "content": e.content,
                     "relevance": e.relevance_score, "confidence": e.confidence}
                    for e in sorted(db.query(EvidenceDB).filter_by(investigation_id=inv.id).all(),
                                    key=lambda e: -e.relevance_score)]

    level = gate.latest_risk_level(db, incident_id)
    requirement = ApprovalPolicy().required_for(level or "CRITICAL")
    satisfied = requirement is Requirement.AUTO or gate.qualifying_approval(db, incident_id, level or "CRITICAL") is not None

    model = to_model(row)
    return {
        "incident": {"id": row.id, "repository": row.repository, "type": row.type, "severity": row.severity,
                     "status": row.status, "attempt": row.attempt or 1, "description": row.description,
                     "metadata": {k: v for k, v in (row.metadata_json or {}).items() if k != "repo_path"},
                     "created_at": _iso(row.created_at), "updated_at": _iso(row.updated_at),
                     "max_attempts": settings.max_attempts()},
        "gate": {"risk_level": level, "approval_required": requirement is not Requirement.AUTO, "satisfied": satisfied},
        "timeline": [_event(e) for e in Lifecycle(db).timeline(incident_id)],
        "investigation": {"id": inv.id, "status": inv.status, "summary": inv.summary} if inv else None,
        "evidence": evidence,
        "diagnoses": [{"id": d.id, "root_cause": d.root_cause, "confidence": d.confidence,
                       "affected_components": d.affected_components, "assumptions": d.assumptions,
                       "unresolved_uncertainty": d.unresolved_uncertainty, "at": _iso(d.created_at)}
                      for d in db.query(DiagnosisDB).filter_by(incident_id=incident_id).order_by(DiagnosisDB.created_at)],
        "risks": [{"id": r.id, "level": r.risk_level, "confidence": r.confidence, "factors": r.factors,
                   "blast_radius": r.blast_radius, "at": _iso(r.created_at)}
                  for r in db.query(RiskAssessmentDB).filter_by(incident_id=incident_id).order_by(RiskAssessmentDB.created_at)],
        "approvals": [{"id": a.id, "decision": a.decision, "risk_level": a.risk_level, "operator": a.operator_name,
                       "reason": a.reason, "at": _iso(a.created_at)}
                      for a in db.query(ApprovalDB).filter_by(incident_id=incident_id).order_by(ApprovalDB.created_at)],
        "remediations": [{"id": r.id, "status": r.status, "branch": r.patch_reference, "base_branch": r.base_branch,
                          "checkpoint_sha": r.checkpoint_sha, "commit_sha": r.commit_sha, "executor": r.executor,
                          "attempt": r.attempt, "changed_files": r.changed_files, "tests_added": r.tests_added,
                          "baseline_failures": r.baseline_failures, "summary": r.summary,
                          "cost_tokens": r.cost_tokens, "rolled_back_at": _iso(r.rolled_back_at)}
                         for r in db.query(RemediationDB).filter_by(incident_id=incident_id).order_by(RemediationDB.created_at)],
        "verifications": [{"id": v.id, "status": v.status, "levels": v.levels, "regressions": v.regressions,
                           "results": v.test_results, "remediation_id": v.remediation_id, "at": _iso(v.created_at)}
                          for v in db.query(VerificationDB).filter_by(incident_id=incident_id).order_by(VerificationDB.created_at)],
        "outcomes": [{"id": o.id, "type": o.prediction_type, "predictor": o.predictor_id, "topic": o.topic,
                      "status": o.status, "confidence": o.confidence, "attempt": o.attempt_number,
                      "components": o.components, "payload": o.prediction_payload, "cost_tokens": o.cost_tokens,
                      "closed_by": o.closed_by, "verification_run_id": o.verification_run_id}
                     for o in db.query(OutcomeRecordDB).filter_by(incident_id=incident_id).order_by(OutcomeRecordDB.predicted_at)],
        "kind": model.type.value,
    }


@router.get("/{incident_id}/remediations/{remediation_id}/diff")
def remediation_diff(incident_id: str, remediation_id: str, db: Session = Depends(get_db)):
    rem = db.get(RemediationDB, remediation_id)
    if rem is None or rem.incident_id != incident_id:
        raise HTTPException(status_code=404, detail="Remediation not found")
    if not (rem.repo_root and rem.checkpoint_sha and rem.commit_sha):
        raise HTTPException(status_code=409, detail="this remediation has no committed patch")
    try:
        # A rolled-back patch is kept reachable under refs/bre/failed/*; a live one is on its bre/* branch.
        return {"branch": rem.patch_reference, "base_sha": rem.checkpoint_sha, "commit_sha": rem.commit_sha,
                "diff": git_ops.diff_between(rem.repo_root, rem.checkpoint_sha, rem.commit_sha)}
    except git_ops.GitError as exc:
        raise HTTPException(status_code=410, detail=f"the patch is no longer available: {exc}")
