"""The state machine's shape, and the lifecycle service as the single gated door.

ERRATA A4/A5: the original transition table had one happy path and no way out, so a
failed remediation stranded the incident. These tests pin the repaired shape, and pin
that the approval gate cannot be walked around by calling the service directly.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile

import pytest
from sqlalchemy import create_engine

from apps.api import database
from apps.api.database import IncidentDB, RiskAssessmentDB, ApprovalDB, generate_id
from models.incident import TERMINAL_STATUSES, VALID_TRANSITIONS, IncidentStatus
from reliability.orchestration.gate import GateViolation
from reliability.orchestration.lifecycle import InvalidTransition, Lifecycle

S = IncidentStatus


def _incident(db, status=S.DETECTED, severity="high") -> IncidentDB:
    row = IncidentDB(
        id=generate_id(), repository="r", type="test_failure", severity=severity,
        status=status.value, description="d", metadata_json={},
    )
    db.add(row)
    db.flush()
    return row


# ── shape of the state machine ────────────────────────────────────────────────


def test_every_state_is_reachable_from_detected():
    seen, frontier = {S.DETECTED}, [S.DETECTED]
    while frontier:
        for nxt in VALID_TRANSITIONS[frontier.pop()]:
            if nxt not in seen:
                seen.add(nxt)
                frontier.append(nxt)
    assert seen == set(S)


def test_every_working_state_has_an_exit_that_is_not_success():
    """The A5 defect: INVESTIGATING and REMEDIATING had only the happy edge."""
    for state in (S.INVESTIGATING, S.DIAGNOSED, S.REMEDIATING, S.VERIFYING, S.REINVESTIGATING):
        exits = set(VALID_TRANSITIONS[state])
        assert exits & {S.FAILED, S.ABANDONED, S.REINVESTIGATING, S.CLOSED}, state


def test_terminal_states_only_lead_to_closed():
    for state in (S.RESOLVED, S.FAILED, S.ABANDONED):
        assert VALID_TRANSITIONS[state] == [S.CLOSED]
    assert VALID_TRANSITIONS[S.CLOSED] == []
    assert S.CLOSED in TERMINAL_STATUSES


def test_a_false_alarm_can_be_closed_from_detected():
    assert S.CLOSED in VALID_TRANSITIONS[S.DETECTED]


# ── the lifecycle service ─────────────────────────────────────────────────────


def test_transition_writes_the_row_and_an_audit_event(db):
    inc = _incident(db)
    Lifecycle(db).transition(inc, S.INVESTIGATING, actor="test", detail={"why": "unit"})
    assert inc.status == "INVESTIGATING"
    [event] = Lifecycle(db).timeline(inc.id)
    assert (event.kind, event.from_status, event.to_status, event.actor) == (
        "transition", "DETECTED", "INVESTIGATING", "test")
    assert event.detail == {"why": "unit"}


def test_illegal_transition_changes_nothing_and_logs_nothing(db):
    inc = _incident(db)
    with pytest.raises(InvalidTransition):
        Lifecycle(db).transition(inc, S.RESOLVED)
    assert inc.status == "DETECTED"
    assert Lifecycle(db).timeline(inc.id) == []


def test_unknown_status_string_is_an_invalid_transition(db):
    with pytest.raises(InvalidTransition):
        Lifecycle(db).transition(_incident(db), "NOT_A_STATE")


def test_gate_cannot_be_bypassed_through_the_service(db):
    """RISK_ASSESSED -> REMEDIATING is a LEGAL edge. Calling the service directly (not the
    HTTP route) must still be refused for a HIGH-risk incident with no approval."""
    inc = _incident(db, S.RISK_ASSESSED)
    db.add(RiskAssessmentDB(id=generate_id(), incident_id=inc.id, risk_level="HIGH", factors={}))
    db.flush()
    with pytest.raises(GateViolation):
        Lifecycle(db).transition(inc, S.REMEDIATING)
    assert inc.status == "RISK_ASSESSED"
    assert Lifecycle(db).timeline(inc.id) == []


def test_attempt_counter_starts_at_one_and_bumps(db):
    inc = _incident(db)
    inc.attempt = None  # a row from before the column existed
    assert Lifecycle(db).bump_attempt(inc) == 2
    assert Lifecycle(db).bump_attempt(inc) == 3


# ── schema migration shim ─────────────────────────────────────────────────────


def test_ensure_columns_upgrades_a_database_that_predates_new_columns():
    path = os.path.join(tempfile.mkdtemp(), "old.db")
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE incidents (id TEXT PRIMARY KEY, repository TEXT NOT NULL, branch TEXT,"
        " type TEXT NOT NULL, severity TEXT, status TEXT, description TEXT NOT NULL,"
        " metadata_json JSON, created_at DATETIME, updated_at DATETIME)"
    )
    con.execute("INSERT INTO incidents (id,repository,type,description) VALUES ('a','r','t','x')")
    con.commit()
    con.close()

    engine = create_engine(f"sqlite:///{path}")
    try:
        database.Base.metadata.create_all(bind=engine)  # leaves the old table untouched
        added = database.ensure_columns(engine)
        assert "incidents.attempt" in added
        with engine.connect() as conn:
            assert conn.exec_driver_sql("select id, attempt from incidents").fetchall() == [("a", 1)]
        assert database.ensure_columns(engine) == []  # idempotent
    finally:
        engine.dispose()
