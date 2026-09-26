"""The routing simulator that tau is tuned on.

It replaces an earlier pair-based tuner that said "never route" for a corpus on which the end-to-end harness showed
routing wins. These tests pin the policy the simulator models; `scripts/tune_tau.py` additionally validates it against
the measured harness artifacts (9 of 9 orderings agreed exactly when it was introduced).
"""

from __future__ import annotations

import pytest

from asmos_bridge.ownership.trust import ownership_score, trust
from asmos_bridge.routing.simulate import Item, orderings, simulate, tune_by_simulation

SAVE, WASTE = 4200.0, 5800.0
COLD = ownership_score(trust(0, 0), 0.0)  # 0.42


def item(i, group, sig="pool exhaustion test", topic="database"):
    return Item(f"i{i}", topic, group, tuple(sig.split()))


def test_cold_start_first_incident_is_never_served_from_memory():
    r = simulate([item(1, "A")], tau=0.0, save=SAVE, waste=WASTE)
    assert (r.served, r.refuted, r.utility) == (0, 0, 0.0)


def test_a_recurring_failure_is_served_from_memory_after_first_sight():
    r = simulate([item(i, "A") for i in range(4)], tau=0.30, save=SAVE, waste=WASTE)
    assert (r.served, r.refuted) == (3, 0) and r.utility == 3 * SAVE
    assert r.routed_ids == ("i1", "i2", "i3")


def test_a_lookalike_is_refuted_and_costs_a_remediation():
    r = simulate([item(1, "A"), item(2, "B")], tau=0.30, save=SAVE, waste=WASTE)
    assert (r.served, r.refuted) == (1, 1) and r.utility == -WASTE


def test_tau_above_every_score_never_routes():
    r = simulate([item(i, "A") for i in range(4)], tau=COLD + 0.01, save=SAVE, waste=WASTE)
    assert (r.served, r.utility) == (0, 0.0)


def test_a_different_topic_is_invisible():
    r = simulate([item(1, "A", topic="db"), item(2, "A", topic="auth")], tau=0.0, save=SAVE, waste=WASTE)
    assert r.served == 0


def test_dissimilar_incidents_are_not_reused():
    r = simulate([item(1, "A", sig="alpha beta gamma"), item(2, "A", sig="delta epsilon zeta")], tau=0.10, save=SAVE, waste=WASTE)
    assert r.served == 0  # similarity 0 -> score 0 < tau, even in the same group


def test_ownership_evolution_stops_a_memory_that_keeps_losing():
    """With ownership evolving, repeated refutations pull the score under tau; frozen never notices."""
    seq = [item(0, "A")] + [item(i, "B") for i in range(1, 30)]
    tau = COLD * 0.97  # just under the cold-start score, so a little decay is enough to cross it
    evolving = simulate(seq, tau, save=SAVE, waste=WASTE)
    frozen = simulate(seq, tau, save=SAVE, waste=WASTE, frozen=True)
    assert frozen.refuted >= evolving.refuted
    assert evolving.utility >= frozen.utility


def test_utility_is_correct_reuses_times_save_minus_refuted_times_waste():
    seq = [item(0, "A"), item(1, "A"), item(2, "B"), item(3, "A")]
    r = simulate(seq, tau=0.30, save=SAVE, waste=WASTE)
    correct = r.served - r.refuted
    assert r.utility == correct * SAVE - r.refuted * WASTE


def test_orderings_are_deterministic_and_the_first_is_the_given_order():
    items = [item(i, "A") for i in range(8)]
    a, b = orderings(items, 5), orderings(items, 5)
    assert a[0] == items and a == b
    assert len({tuple(x.id for x in o) for o in a}) > 1


def test_tuner_chooses_reuse_when_reuse_pays():
    items = [item(i, "A") for i in range(6)]
    t = tune_by_simulation(items, save=SAVE, waste=WASTE, n_orderings=8)
    assert t.mean_utility > 0 and t.tau <= COLD and not t.note


def test_tuner_says_never_route_when_every_reuse_would_be_wrong():
    # every incident is its own scenario but they all look the same: any reuse is a refutation
    items = [item(i, f"G{i}") for i in range(6)]
    t = tune_by_simulation(items, save=SAVE, waste=WASTE, n_orderings=8)
    assert t.mean_utility <= 0 and "never" in t.note and t.tau > COLD


def test_tuner_ties_break_toward_the_stricter_tau():
    items = [item(i, "A") for i in range(5)]
    t = tune_by_simulation(items, save=SAVE, waste=WASTE, n_orderings=6)
    best = max(c["mean_utility"] for c in t.curve)
    same = [c["tau"] for c in t.curve if c["mean_utility"] == best]
    assert t.tau == max(same)
