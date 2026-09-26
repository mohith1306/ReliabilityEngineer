"""The bridge must return exactly what real ASMOS returns.

ADR-0001 chose a vendored re-implementation over a package dependency, on the condition that
"identical to ASMOS" is a test rather than an intention. The vectors below were generated
FROM the ASMOS source by scripts/gen_asmos_parity_vectors.py; see `provenance` in the JSON for
the ASMOS commit they came from.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from asmos_bridge.ownership import reputation, trust

DATA = json.loads((Path(__file__).parent / "asmos_parity_vectors.json").read_text(encoding="utf-8"))
V = DATA["vectors"]


def test_vectors_carry_provenance_and_are_not_empty():
    assert DATA["provenance"]["asmos_git_sha"] != "unknown"
    assert all(len(v) > 0 for v in V.values())
    assert DATA["constants"] == {"alpha": trust.ALPHA, "beta": trust.BETA}


@pytest.mark.parametrize("v", V["trust"])
def test_trust_matches_asmos(v):
    assert trust.trust(v["vc"], v["vt"]) == v["expected"]


@pytest.mark.parametrize("v", V["ownership"])
def test_ownership_matches_asmos(v):
    assert trust.ownership_score(v["expertise"], v["share"]) == v["expected"]


@pytest.mark.parametrize("v", V["routing_score"])
def test_routing_score_matches_asmos(v):
    assert trust.routing_score(v["sim"], v["ownership"]) == v["expected"]


@pytest.mark.parametrize("v", V["routing_decision"])
def test_routing_decision_matches_asmos(v):
    got = trust.routing_decision([tuple(o) for o in v["owners"]], v["tau"], v["k"])
    got["owners"] = [list(o) for o in got["owners"]]
    assert got == v["expected"]


@pytest.mark.parametrize("v", V["reputation"])
def test_reputation_update_matches_asmos(v):
    got = reputation.reputation_update(v["claim_class"], v["status"])
    assert [got.verified_correct_delta, got.verified_total_delta] == v["expected"]


# ── properties that follow from the equations (not parity, but they must hold) ────────────────


def test_cold_start_trust_is_seventy_percent():
    assert trust.trust(0, 0) == 0.7


def test_refutation_lowers_trust_and_verification_raises_it():
    base = trust.trust(5, 10)
    assert trust.trust(6, 11) > base      # one more verified-correct
    assert trust.trust(5, 11) < base      # one more observation, wrong


def test_invalid_counts_are_rejected():
    with pytest.raises(ValueError):
        trust.trust(3, 2)
    with pytest.raises(ValueError):
        trust.trust(-1, 2)


def test_class_c_never_moves_reputation_even_when_verified():
    for status in ("verified", "refuted", "confirmed"):
        u = reputation.reputation_update("C", status)
        assert (u.verified_correct_delta, u.verified_total_delta) == (0.0, 0.0)


def test_pending_and_abandoned_move_nothing_invariant_3():
    for cls in ("A", "B"):
        for status in ("pending", "abandoned"):
            u = reputation.reputation_update(cls, status)
            assert (u.verified_correct_delta, u.verified_total_delta) == (0.0, 0.0)
