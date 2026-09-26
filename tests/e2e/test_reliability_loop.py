"""S7 -- the whole loop, end to end, on real git repositories.

Exit criteria (docs/stages/STAGES.md):
  * targeted / component / regression levels run and are distinguishable in the result
  * a verification failure transitions the incident to REINVESTIGATING
  * the loop carries an attempt counter with a hard cap; a test proves it terminates
  * rollback restores the checkpoint and sets the remediation to ROLLED_BACK

Bob is replaced by its labelled replay stand-in (BRE_BOB_TRANSPORT=replay); everything else --
the git checkpoint, the branch, the diff guard, pytest in the target, the ledger -- is real.
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from apps.api.database import (
    ApprovalDB, IncidentDB, IncidentEventDB, OperatorDB, OutcomeRecordDB, RemediationDB,
    RiskAssessmentDB, VerificationDB, generate_id,
)
from bob.errors import BobNotAvailable
from models.diagnosis import Diagnosis
from reliability.orchestration.loop import DiagnoseResult, ReliabilityLoop
from reliability.remediation import git_ops
from reliability.remediation.allowlist import RepoAllowlist
from reliability.remediation.executors import ExecutorResult, ReplayExecutor
from reliability.verification.verifier import max_attempts


@pytest.fixture(autouse=True)
def _replay(monkeypatch):
    monkeypatch.setenv("BRE_BOB_TRANSPORT", "replay")
    monkeypatch.delenv("BRE_MAX_ATTEMPTS", raising=False)


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


# ── the happy path: a human is in the loop, and the fix is verified ───────────────────────


def test_high_risk_incident_waits_for_a_human_and_nothing_is_written(db, seeded_repo):
    inc = incident(db, seeded_repo)
    base = (git_ops.current_branch(seeded_repo), git_ops.head_sha(seeded_repo))

    res = make_loop(db, seeded_repo).advance(inc.id)

    assert [s.action for s in res.steps] == ["investigate", "diagnose", "assess_risk", "request_approval"]
    assert res.blocked_on == "approval" and res.status == "AWAITING_APPROVAL"
    assert (git_ops.current_branch(seeded_repo), git_ops.head_sha(seeded_repo)) == base
    assert git(seeded_repo, "branch", "--list", "bre/*") == ""  # analysis is free; mutation is privileged
    pending = {r.prediction_type: r for r in records(db, inc)}
    assert set(pending) == {"diagnosis", "risk_level"} and all(r.status == "pending" for r in pending.values())
    assert pending["diagnosis"].cost_tokens == 4200 and pending["diagnosis"].components["simulated"] is True


def test_full_lifecycle_resolves_and_only_verification_closes_outcomes(db, seeded_repo):
    inc = incident(db, seeded_repo)
    base_branch, base_sha = git_ops.current_branch(seeded_repo), git_ops.head_sha(seeded_repo)

    res = drive(db, make_loop(db, seeded_repo), inc)

    assert res.status == "RESOLVED" and inc.status == "RESOLVED"
    # the user's checkout is handed back, untouched; the fix lives on a bre/* branch for review
    assert git_ops.current_branch(seeded_repo) == base_branch and git_ops.head_sha(seeded_repo) == base_sha
    branch = f"bre/{inc.id}/attempt-1"
    assert "pool_size: 20" in git(seeded_repo, "show", f"{branch}:config/app.yaml")
    assert "pool_size: 2\n" in (seeded_repo / "config/app.yaml").read_text(encoding="utf-8").replace("\r\n", "\n")

    # every prediction closed CONFIRMED, by a REAL verification run
    run = db.query(VerificationDB).filter_by(incident_id=inc.id).one()
    assert run.status == "passed"
    recs = records(db, inc)
    assert {r.prediction_type for r in recs} == {"diagnosis", "risk_level", "remediation_plan"}
    assert all(r.status == "confirmed" and r.verification_run_id == run.id for r in recs)
    assert all(r.closed_by == "verification-engine" for r in recs)


def test_the_three_levels_are_distinguishable_in_the_result(db, seeded_repo):
    inc = incident(db, seeded_repo)
    drive(db, make_loop(db, seeded_repo), inc)
    levels = db.query(VerificationDB).filter_by(incident_id=inc.id).one().levels
    assert [k for k in levels if k != "verdict"] == ["targeted", "component", "regression"]
    assert levels["targeted"]["selectors"] == ["tests/test_dbpool.py::test_pool_sized_from_config"]
    assert levels["targeted"]["fixed"] == ["tests/test_dbpool.py::test_pool_sized_from_config"]
    assert levels["component"]["selectors"] == ["tests/test_dbpool.py"]  # the whole file, not the node
    assert levels["regression"]["selectors"] == [] and levels["regression"]["ran"] >= 2
    assert all(v["ok"] for k, v in levels.items() if k != "verdict")


def test_the_audit_trail_tells_the_whole_story_in_order(db, seeded_repo):
    inc = incident(db, seeded_repo)
    drive(db, make_loop(db, seeded_repo), inc)
    trail = [(e.kind, e.to_status) for e in db.query(IncidentEventDB).filter_by(incident_id=inc.id).order_by(IncidentEventDB.id)]
    transitions = [to for kind, to in trail if kind == "transition"]
    assert transitions == ["INVESTIGATING", "DIAGNOSED", "RISK_ASSESSED", "AWAITING_APPROVAL",
                           "REMEDIATING", "VERIFYING", "RESOLVED"]
    kinds = [k for k, _ in trail]
    assert kinds.index("remediation") < kinds.index("verification")
    approvers = {e.actor for e in db.query(IncidentEventDB).filter_by(incident_id=inc.id, to_status="REMEDIATING")}
    assert approvers == {"dana (test operator)"}  # the gate's identity is in the record, not a free-text field


def test_low_risk_needs_no_approval(db, seeded_repo):
    inc = incident(db, seeded_repo, severity="low")

    def diagnoser(req):  # no affected components -> blast radius 0 -> LOW
        d = Diagnosis(id="dx-1", incident_id=req.incident.id, root_cause="pool_size lowered",
                      confidence=0.9, affected_components=[], assumptions=["x"])
        return DiagnoseResult(d, "test-source")

    res = drive(db, make_loop(db, seeded_repo, diagnoser=diagnoser), inc, approve=False)
    risk = db.query(RiskAssessmentDB).filter_by(incident_id=inc.id).one()
    assert risk.risk_level == "LOW"
    assert res.status == "RESOLVED"
    assert db.query(ApprovalDB).filter_by(incident_id=inc.id).count() == 0


def test_rejection_closes_the_incident_and_writes_nothing(db, seeded_repo):
    inc = incident(db, seeded_repo)
    loop = make_loop(db, seeded_repo)
    loop.advance(inc.id)
    decide(db, inc, "REJECTED", "not during the freeze")
    res = loop.advance(inc.id)
    db.refresh(inc)
    assert inc.status == "CLOSED" and res.steps[-1].action == "rejected"
    assert git(seeded_repo, "branch", "--list", "bre/*") == ""
    assert {r.status for r in records(db, inc)} == {"abandoned"}  # nothing tested them: no reputation moves


# ── failure: refute, roll back, retry, and STOP ──────────────────────────────────────────


def test_a_failed_verification_rolls_back_refutes_and_reinvestigates(db, seeded_repo):
    inc = incident(db, seeded_repo)
    base_branch, base_sha = git_ops.current_branch(seeded_repo), git_ops.head_sha(seeded_repo)
    ex = Recorder(useless_patch)

    loop = make_loop(db, seeded_repo, executor_factory=lambda: ex)
    loop.advance(inc.id)
    decide(db, inc)
    res = loop.advance(inc.id)
    db.refresh(inc)

    actions = [s.action for s in res.steps]
    assert actions[:3] == ["approved", "remediate", "verify"]
    assert res.steps[2].data["passed"] is False
    # a failed verification -> REINVESTIGATING, and the loop then does the whole cycle again on its
    # own, arriving back at the human gate with a NEW assessment that needs a NEW approval
    assert actions[3:] == ["investigate", "diagnose", "assess_risk", "request_approval"]
    transitions = [e.to_status for e in db.query(IncidentEventDB).filter_by(incident_id=inc.id, kind="transition")
                   .order_by(IncidentEventDB.id)]
    assert "REINVESTIGATING" in transitions
    assert inc.status == "AWAITING_APPROVAL" and inc.attempt == 2 and res.blocked_on == "approval"
    # rolled back exactly
    assert (git_ops.current_branch(seeded_repo), git_ops.head_sha(seeded_repo)) == (base_branch, base_sha)
    assert git(seeded_repo, "branch", "--list", "bre/*") == ""
    rem = db.query(RemediationDB).filter_by(incident_id=inc.id).one()
    assert rem.status == "rolled_back" and rem.rolled_back_at
    assert git(seeded_repo, "rev-parse", "--verify", f"refs/bre/failed/{inc.id}-attempt-1")  # kept as evidence
    # a NEGATIVE result was recorded, against a real run, by the verifier
    run = db.query(VerificationDB).filter_by(incident_id=inc.id).one()
    assert run.status == "failed" and run.levels["targeted"]["ok"] is False
    assert run.levels["component"]["skipped"] and run.levels["regression"]["skipped"]  # fail-fast, and visible
    recs = records(db, inc)
    assert {r.status for r in recs if r.attempt_number == 1} == {"refuted"}
    assert {r.status for r in recs if r.attempt_number == 2} == {"pending"}  # attempt 2 is new and untested


def test_the_loop_terminates_at_the_attempt_cap(db, seeded_repo):
    """A patch that can never work must not run forever. Cap = 3 -> exactly 3 tries, then ABANDONED."""
    inc = incident(db, seeded_repo)
    ex = Recorder(useless_patch)
    base = (git_ops.current_branch(seeded_repo), git_ops.head_sha(seeded_repo))

    res = drive(db, make_loop(db, seeded_repo, executor_factory=lambda: ex), inc)

    assert inc.status == "ABANDONED" and res.blocked_on == "terminal"
    assert ex.calls == max_attempts() == 3  # the executor was invoked exactly `cap` times, never more
    assert inc.attempt == 3
    assert (git_ops.current_branch(seeded_repo), git_ops.head_sha(seeded_repo)) == base
    assert git(seeded_repo, "branch", "--list", "bre/*") == ""
    rems = db.query(RemediationDB).filter_by(incident_id=inc.id).all()
    assert len(rems) == 3 and {r.status for r in rems} == {"rolled_back"}
    recs = records(db, inc)
    assert not [r for r in recs if r.status == "pending"], "an abandoned incident must leave nothing pending"
    assert {r.attempt_number for r in recs} == {1, 2, 3}
    assert {r.status for r in recs} == {"refuted"}  # three real, verified negatives


def test_the_cap_is_configurable_and_never_below_one(db, seeded_repo, monkeypatch):
    monkeypatch.setenv("BRE_MAX_ATTEMPTS", "1")
    inc = incident(db, seeded_repo)
    ex = Recorder(useless_patch)
    drive(db, make_loop(db, seeded_repo, executor_factory=lambda: ex), inc)
    assert inc.status == "ABANDONED" and ex.calls == 1
    monkeypatch.setenv("BRE_MAX_ATTEMPTS", "0")
    assert max_attempts() == 1
    monkeypatch.setenv("BRE_MAX_ATTEMPTS", "banana")
    assert max_attempts() == 3


def test_the_next_diagnosis_is_told_what_already_failed(db, seeded_repo):
    inc = incident(db, seeded_repo)
    seen = []

    def diagnoser(req):
        seen.append((req.attempt, list(req.prior_attempts)))
        from reliability.orchestration.loop import bob_diagnoser
        return bob_diagnoser(req)

    drive(db, make_loop(db, seeded_repo, diagnoser=diagnoser, executor_factory=lambda: Recorder(useless_patch)), inc)
    assert seen[0] == (1, [])
    attempt2_prior = seen[1][1]
    assert attempt2_prior[0]["attempt"] == 1 and "targeted" in attempt2_prior[0]["why_failed"]


def test_an_attempt_that_never_reached_verification_is_abandoned_not_refuted(db, seeded_repo):
    """The executor changed nothing. No test ever ran against a fix, so no prediction was tested."""
    inc = incident(db, seeded_repo)
    ex = Recorder(lambda root: None)
    drive(db, make_loop(db, seeded_repo, executor_factory=lambda: ex), inc)
    assert inc.status == "FAILED"  # remediation itself failed 3 times: a different terminal than ABANDONED
    assert ex.calls == 3
    assert not {r.status for r in records(db, inc)} & {"confirmed", "refuted"}
    assert {r.status for r in records(db, inc)} == {"abandoned"}


def test_no_reproducing_test_means_no_verified_fix(db, seeded_repo):
    """Heal the repo first: nothing fails at baseline, so there is nothing to show a patch fixed.
    The loop must refuse to call that a success, however plausible the patch looks."""
    (seeded_repo / "config/app.yaml").write_bytes(
        (seeded_repo / "config/app.yaml").read_bytes().replace(b"pool_size: 2", b"pool_size: 20"))
    git(seeded_repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "heal config")
    inc = incident(db, seeded_repo)

    def diagnoser(req):
        d = Diagnosis(id=f"dx-{generate_id()}", incident_id=req.incident.id, root_cause="unknown", confidence=0.4,
                      affected_components=["dbpool.py"], assumptions=["guess"])
        return DiagnoseResult(d, "test-source")

    ex = Recorder(useless_patch)
    drive(db, make_loop(db, seeded_repo, diagnoser=diagnoser, executor_factory=lambda: ex), inc)
    run = db.query(VerificationDB).first()
    assert run.status == "failed" and "no reproducing test" in run.levels["verdict"]["reason"]
    assert inc.status == "ABANDONED"


# ── the loop stops, rather than guesses, when something outside it is missing ────────────


def test_no_allowlist_means_the_loop_stops_at_remediating(db, seeded_repo):
    inc = incident(db, seeded_repo)
    loop = make_loop(db, seeded_repo, allowlist=RepoAllowlist([]))
    loop.advance(inc.id)
    decide(db, inc)
    res = loop.advance(inc.id)
    db.refresh(inc)
    assert res.blocked_on == "allowlist" and inc.status == "REMEDIATING"
    assert git(seeded_repo, "branch", "--list", "bre/*") == ""


def test_bob_unavailable_is_a_block_not_a_failure(db, seeded_repo, monkeypatch):
    inc = incident(db, seeded_repo)

    def diagnoser(req):
        raise BobNotAvailable("no Bob here")

    res = make_loop(db, seeded_repo, diagnoser=diagnoser).advance(inc.id)
    db.refresh(inc)
    assert res.blocked_on == "bob_unavailable" and inc.status == "INVESTIGATING"  # retryable, nothing burned


def test_step_budget_bounds_a_single_call(db, seeded_repo):
    inc = incident(db, seeded_repo)
    res = make_loop(db, seeded_repo).advance(inc.id, max_steps=2)
    assert len(res.steps) == 2 and res.blocked_on == "budget"
