"""Outcome ledger, persisted: open at prediction time, closed by verification.

ADR-0003 exit criteria for S3, exercised against a real database rather than
the in-memory model tests of tests/unit/test_outcome_ledger.py:

    - OutcomeRecord model + table; diagnosis / risk / routing predictions open
      with status=pending
    - a verification result closes the matching records to confirmed / refuted
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.database import Base, VerificationDB
from models.outcome import OutcomeRecordCreate, OutcomeStatus, PredictionType
from reliability.ledger.query import accuracy_by, cost_rollup
from reliability.ledger.record import (
    OutcomeLedger,
    open_diagnosis_prediction,
    open_risk_prediction,
    open_routing_prediction,
)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _prediction(**overrides) -> OutcomeRecordCreate:
    base = dict(
        incident_id="inc_1",
        predictor_id="bob",
        topic="database",
        prediction_type=PredictionType.DIAGNOSIS,
        confidence=0.9,
        components={"evidence": 0.8, "history": 0.4},
    )
    base.update(overrides)
    return OutcomeRecordCreate(**base)


def _verification_run(db, incident_id: str = "inc_1", run_id: str = "ver_1"):
    row = VerificationDB(
        id=run_id,
        incident_id=incident_id,
        remediation_id="rem_1",
        status="passed",
    )
    db.add(row)
    db.commit()
    return run_id


# ── prediction-time opens (S3 exit criterion 1) ───────────────────────────────

def test_diagnosis_risk_and_routing_all_open_pending(db):
    """Every prediction type opens pending -- the obligation S4/S5/S8 inherit."""
    ledger = OutcomeLedger(db)
    d = open_diagnosis_prediction(
        db, incident_id="inc_1", predictor_id="bob", topic="database",
        root_cause="pool exhaustion", confidence=0.9,
        components={"evidence": 0.8},
    )
    r = open_risk_prediction(
        db, incident_id="inc_1", predictor_id="risk-classifier", topic="database",
        risk_level="HIGH", confidence=0.8, components={"blast_radius": 3},
    )
    rt = open_routing_prediction(
        db, incident_id="inc_1", predictor_id="asmos", topic="database",
        routed_to="bob", confidence=0.7, components={"ownership": 0.6},
    )
    db.commit()

    for record in (d, r, rt):
        assert record.status is OutcomeStatus.PENDING
        assert ledger.get(record.id).status is OutcomeStatus.PENDING

    pending = ledger.pending_for_incident("inc_1")
    assert len(pending) == 3
    assert {p.prediction_type for p in pending} == {
        PredictionType.DIAGNOSIS, PredictionType.RISK_LEVEL, PredictionType.ROUTING,
    }


def test_open_rejects_scored_prediction_without_components(db):
    """ASMOS Invariant 8: a bare confidence scalar is unauditable."""
    with pytest.raises(ValueError, match="component breakdown"):
        OutcomeLedger(db).open(_prediction(confidence=0.9, components={}))


def test_unscored_prediction_needs_no_components(db):
    record = OutcomeLedger(db).open(_prediction(confidence=0.0, components={}))
    assert record.status is OutcomeStatus.PENDING


# ── verification closes (S3 exit criterion 2) ─────────────────────────────────

def test_verification_pass_closes_all_pending_as_confirmed(db):
    run = _verification_run(db)
    ledger = OutcomeLedger(db)
    open_diagnosis_prediction(
        db, incident_id="inc_1", predictor_id="bob", topic="database",
        root_cause="pool exhaustion", confidence=0.9, components={"evidence": 0.8},
    )
    open_risk_prediction(
        db, incident_id="inc_1", predictor_id="risk-classifier", topic="database",
        risk_level="HIGH", confidence=0.8, components={"blast": 3},
    )
    db.commit()

    closed = ledger.close_for_verification("inc_1", run, passed=True, closed_by="pytest")
    db.commit()

    assert len(closed) == 2
    for record in closed:
        assert record.status is OutcomeStatus.CONFIRMED
        assert record.closed_by == "pytest"
        assert record.verification_run_id == run
        assert record.closed_at is not None
    assert ledger.pending_for_incident("inc_1") == []


def test_verification_failure_refutes(db):
    run = _verification_run(db)
    ledger = OutcomeLedger(db)
    open_diagnosis_prediction(
        db, incident_id="inc_1", predictor_id="bob", topic="database",
        root_cause="wrong hypothesis", confidence=0.9, components={"evidence": 0.8},
    )
    db.commit()

    closed = ledger.close_for_verification("inc_1", run, passed=False, closed_by="pytest")
    db.commit()
    assert [c.status for c in closed] == [OutcomeStatus.REFUTED]


def test_close_for_verification_requires_a_real_run(db):
    ledger = OutcomeLedger(db)
    open_diagnosis_prediction(
        db, incident_id="inc_1", predictor_id="bob", topic="database",
        root_cause="x", confidence=0.5, components={"a": 1},
    )
    db.commit()
    with pytest.raises(ValueError, match="verification run not found"):
        ledger.close_for_verification("inc_1", "ver_missing", passed=True, closed_by="t")


def test_close_for_verification_rejects_run_from_another_incident(db):
    _verification_run(db, incident_id="inc_other", run_id="ver_other")
    ledger = OutcomeLedger(db)
    open_diagnosis_prediction(
        db, incident_id="inc_1", predictor_id="bob", topic="database",
        root_cause="x", confidence=0.5, components={"a": 1},
    )
    db.commit()
    with pytest.raises(ValueError, match="belongs to incident"):
        ledger.close_for_verification("inc_1", "ver_other", passed=True, closed_by="t")


# ── structural guards ─────────────────────────────────────────────────────────

def test_closing_to_confirmed_without_run_is_rejected(db):
    ledger = OutcomeLedger(db)
    record = ledger.open(_prediction())
    db.commit()
    with pytest.raises(ValueError, match="verification_run_id"):
        ledger.close(record.id, OutcomeStatus.CONFIRMED, closed_by="t")


def test_close_validates_run_existence(db):
    ledger = OutcomeLedger(db)
    record = ledger.open(_prediction())
    db.commit()
    with pytest.raises(ValueError, match="does not exist"):
        ledger.close(
            record.id, OutcomeStatus.CONFIRMED,
            closed_by="t", verification_run_id="ver_nope",
        )


def test_eval_run_prefix_is_accepted_without_a_row(db):
    """The evaluation harness is a verifier of record for corpus runs (pre-S7)."""
    ledger = OutcomeLedger(db)
    record = ledger.open(_prediction())
    db.commit()
    closed = ledger.close(
        record.id, OutcomeStatus.CONFIRMED,
        closed_by="evaluation-harness", verification_run_id="eval:run-1",
    )
    assert closed.status is OutcomeStatus.CONFIRMED


def test_abandoned_needs_no_run(db):
    """Loop cap is an outcome, not a verification."""
    ledger = OutcomeLedger(db)
    ledger.open(_prediction())
    db.commit()
    n = ledger.abandon_pending("inc_1", closed_by="attempt-cap")
    db.commit()
    assert n == 1


def test_double_close_is_rejected_at_the_ledger(db):
    _verification_run(db)
    ledger = OutcomeLedger(db)
    record = ledger.open(_prediction())
    db.commit()
    ledger.close(
        record.id, OutcomeStatus.CONFIRMED,
        closed_by="t", verification_run_id="eval:r1",
    )
    with pytest.raises(ValueError, match="already"):
        ledger.close(
            record.id, OutcomeStatus.REFUTED,
            closed_by="t", verification_run_id="eval:r2",
        )


# ── query rollups (the inputs to ARCHITECTURE.md section 30) ─────────────────

def test_accuracy_rollup_by_predictor(db):
    _verification_run(db)
    ledger = OutcomeLedger(db)
    open_diagnosis_prediction(
        db, incident_id="inc_1", predictor_id="bob", topic="database",
        root_cause="a", confidence=0.9, components={"e": 1},
    )
    open_diagnosis_prediction(
        db, incident_id="inc_1", predictor_id="bob", topic="database",
        root_cause="b", confidence=0.7, components={"e": 1},
    )
    open_risk_prediction(
        db, incident_id="inc_1", predictor_id="risk-classifier", topic="database",
        risk_level="HIGH", confidence=0.8, components={"b": 1},
    )
    db.commit()

    ledger.close_for_verification("inc_1", "ver_1", passed=True, closed_by="t")
    db.commit()

    rows = accuracy_by(db, "predictor_id")
    by_predictor = {r["predictor_id"]: r for r in rows}
    assert by_predictor["bob"]["confirmed"] == 2
    assert by_predictor["bob"]["accuracy"] == 1.0
    assert by_predictor["risk-classifier"]["confirmed"] == 1


def test_cost_rollup_counts_tokens_and_wall_time(db):
    ledger = OutcomeLedger(db)
    ledger.open(_prediction(), cost_tokens=1200, cost_wall_ms=42.5)
    ledger.open(_prediction(), cost_tokens=300, cost_wall_ms=7.5)
    db.commit()

    rollup = cost_rollup(db)
    assert rollup["records"] == 2
    assert rollup["total_tokens"] == 1500
    assert rollup["total_wall_ms"] == 50.0
    assert rollup["by_predictor"]["bob"]["records"] == 2
