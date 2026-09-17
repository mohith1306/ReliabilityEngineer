"""Outcome ledger invariants (ADR-0003).

These encode the rules that make the ledger trustworthy. If one of these fails, the
learning loop and every metric in ARCHITECTURE.md section 30 are built on sand.

Not yet executed: the dev environment for this repo has no dependencies installed
(see session 0001 entry #10). Run with `pytest tests/unit/test_outcome_ledger.py`
once `pip install -r requirements.txt` has been done.
"""

import pytest

from models.outcome import (
    ClaimClass,
    OutcomeRecord,
    OutcomeStatus,
    PredictionType,
)


def _record(**overrides) -> OutcomeRecord:
    base = dict(
        id="out_1",
        incident_id="inc_1",
        predictor_id="bob",
        topic="auth",
        prediction_type=PredictionType.DIAGNOSIS,
        claim_class=ClaimClass.B,
        confidence=0.9,
        components={"evidence": 0.8, "history": 0.4},
    )
    base.update(overrides)
    return OutcomeRecord(**base)


def test_opens_pending():
    """A prediction is unresolved until something verifies it."""
    assert _record().status is OutcomeStatus.PENDING


def test_pending_never_moves_reputation():
    """ASMOS Invariant 3: generation changes nothing."""
    assert _record().moves_reputation is False


def test_verified_outcome_moves_reputation():
    r = _record()
    r.close(OutcomeStatus.CONFIRMED, closed_by="pytest", verification_run_id="ver_1")
    assert r.is_closed
    assert r.moves_reputation is True
    assert r.closed_at is not None


def test_refuted_outcome_also_moves_reputation():
    """A refutation is signal, not silence -- it lowers ownership."""
    r = _record()
    r.close(OutcomeStatus.REFUTED, closed_by="pytest")
    assert r.moves_reputation is True


def test_class_c_never_moves_reputation_even_when_verified():
    """Speculation stays speculation, however it turns out."""
    r = _record(claim_class=ClaimClass.C)
    r.close(OutcomeStatus.CONFIRMED, closed_by="pytest")
    assert r.is_closed
    assert r.moves_reputation is False


def test_abandoned_is_terminal():
    """The loop hitting its attempt cap is a real outcome, not a missing one."""
    r = _record()
    r.close(OutcomeStatus.ABANDONED, closed_by="loop-cap")
    assert r.is_closed


def test_cannot_close_to_pending():
    with pytest.raises(ValueError, match="not terminal"):
        _record().close(OutcomeStatus.PENDING, closed_by="pytest")


def test_cannot_reclose():
    """Corrections supersede; they never overwrite."""
    r = _record()
    r.close(OutcomeStatus.CONFIRMED, closed_by="pytest")
    with pytest.raises(ValueError, match="already"):
        r.close(OutcomeStatus.REFUTED, closed_by="someone-else")


def test_confidence_is_bounded():
    with pytest.raises(Exception):
        _record(confidence=1.4)


def test_cost_fields_exist_from_the_start():
    """ERRATA A8: cost cannot be reconstructed after the fact."""
    r = _record()
    assert hasattr(r, "cost_tokens") and hasattr(r, "cost_wall_ms")


def test_tenant_carried_even_in_single_tenant_mvp():
    """ERRATA A7: retrofitting tenancy after the ledger has data is expensive."""
    assert _record().tenant_id == "default"
