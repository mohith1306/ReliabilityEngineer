"""Shared scaffolding for tests that drive the reliability loop on real git repositories."""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from apps.api.database import (
    ApprovalDB, IncidentDB, OperatorDB, OutcomeRecordDB, RiskAssessmentDB, generate_id,
)
from reliability.orchestration.loop import ReliabilityLoop
from reliability.remediation.allowlist import RepoAllowlist
from reliability.remediation.executors import ExecutorResult, ReplayExecutor


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def incident(db, repo, *, severity="high") -> IncidentDB:
    row = IncidentDB(
        id=generate_id(), repository="seeded_failure", type="test_failure", severity=severity, status="DETECTED",
        description="DatabaseConnector test failed: connection pool exhaustion in tests/test_dbpool.py",
        metadata_json={"repo_path": str(repo), "ci_log": "ci/failure.log", "topic": "database",
                       "error": "AssertionError: connection pool exhausted after 2 acquisitions"},
    )
    db.add(row)
    db.commit()
    return row


def operator(db) -> OperatorDB:
    op = db.query(OperatorDB).first()
    if op is None:
        op = OperatorDB(id=generate_id(), name="dana (test operator)", api_key_hash="x" * 64)
        db.add(op)
        db.commit()
    return op


def decide(db, inc, decision="APPROVED", reason=None):
    """What POST /approvals does after authentication: a row carrying a verified operator identity."""
    op = operator(db)
    level = db.query(RiskAssessmentDB).filter_by(incident_id=inc.id).order_by(
        RiskAssessmentDB.created_at.desc()).first().risk_level
    db.add(ApprovalDB(id=generate_id(), incident_id=inc.id, risk_level=level, decision=decision,
                      operator_id=op.id, operator_name=op.name, reason=reason, created_at=datetime.utcnow()))
    db.commit()


def make_loop(db, repo, **kw):
    kw.setdefault("allowlist", RepoAllowlist([repo.parent]))
    kw.setdefault("executor_factory", ReplayExecutor)
    return ReliabilityLoop(db, **kw)


def drive(db, loop, inc, *, approve=True, limit=12):
    """Advance; whenever the loop asks for a human, act as one. Bounded, so a runaway loop fails
    the test instead of hanging it."""
    for _ in range(limit):
        res = loop.advance(inc.id)
        db.refresh(inc)
        if res.blocked_on == "approval" and approve:
            decide(db, inc)
            continue
        return res
    pytest.fail(f"loop did not settle within {limit} advances; status={inc.status}")


class Recorder:
    """An executor that records calls and does a useless-but-plausible thing."""

    name = "fake"

    def __init__(self, act):
        self.act, self.calls = act, 0

    def apply(self, prompt, *, repo_root):
        self.calls += 1
        self.act(Path(repo_root))
        return ExecutorResult(summary="add a defensive comment", tokens=100, wall_ms=1.0, provider="fake")


def useless_patch(root):
    p = root / "dbpool.py"
    p.write_bytes(p.read_bytes() + b"\n# TODO: revisit pool sizing\n")


def records(db, inc):
    return db.query(OutcomeRecordDB).filter_by(incident_id=inc.id).order_by(OutcomeRecordDB.predicted_at).all()
