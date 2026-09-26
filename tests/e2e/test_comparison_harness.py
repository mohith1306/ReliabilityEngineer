"""The BRE-vs-Bob-alone comparison harness (S9): small, real, and deterministic.

A three-incident corpus is enough to exercise every arm through the real loop (real git, real pytest): two recurrences of
one failure and one look-alike of it. Full-corpus numbers live in docs/RESULTS.md, from `python -m reliability.evaluation.compare`.
"""

from __future__ import annotations

import pytest

from reliability.evaluation import compare
from reliability.evaluation.run import load_corpus

SEEDS = ("seed-001", "seed-002", "seed-011")  # recurrence, recurrence, look-alike of the first


@pytest.fixture(scope="module")
def specs():
    by_id = {s["id"]: s for s in load_corpus("tests/e2e/corpus")}
    return [by_id[i] for i in SEEDS]


@pytest.fixture(scope="module")
def result(specs):
    with compare._env(BRE_BOB_TRANSPORT="replay", BRE_TAU="0.10", BRE_MAX_ATTEMPTS=None):
        return compare.compare(specs, n_orderings=1)


def test_every_arm_resolves_every_incident_and_bob_alone_never_touches_memory(result):
    arms = result["runs"][0]["arms"]
    assert set(arms) == set(compare.ARMS)
    for arm, data in arms.items():
        assert data["summary"]["resolution_rate"] == 1.0, (arm, data["summary"]["not_resolved"])
    b = arms["baseline"]["summary"]
    assert b["memory_diagnoses"] == 0 and b["bob_diagnoses"] == 3 and b["wasted_attempts"] == 0


def test_bre_reuses_a_recurrence_and_the_tests_refute_the_lookalike(result):
    inc = {i["id"]: i for i in result["runs"][0]["arms"]["bre"]["incidents"]}
    assert inc["seed-001"]["served_from_memory"] is False          # first sight: a full investigation
    assert inc["seed-002"]["served_from_memory"] is True           # the recurrence: verified memory, 0 Bob diagnosis tokens
    assert inc["seed-002"]["diagnosis_tokens"] == 0
    lookalike = inc["seed-011"]
    assert lookalike["memory_refuted"] == 1 and lookalike["attempts"] == 2   # refuted, rolled back, re-investigated
    assert lookalike["resolved"] is True and lookalike["served_from_memory"] is False


def test_bre_costs_no_more_than_bob_alone_here_and_wastes_exactly_one_attempt(result):
    s = result["runs"][0]["arms"]
    assert s["bre"]["summary"]["wasted_attempts"] == 1 and s["baseline"]["summary"]["wasted_attempts"] == 0
    assert s["bre"]["summary"]["memory_diagnoses"] == 2 and s["bre"]["summary"]["memory_refuted"] == 1


def test_the_ablation_arm_runs_and_is_reported_separately(result):
    frozen = result["runs"][0]["arms"]["bre_frozen"]["summary"]
    assert frozen["memory_refuted"] >= result["runs"][0]["arms"]["bre"]["summary"]["memory_refuted"]


def test_findings_are_generated_from_the_numbers_and_carry_the_cost_caveat(result):
    lines = compare.verdict(result)
    assert lines and any("NOMINAL" in line for line in lines)
    assert any("Wasted (failed) attempts" in line for line in lines)


def test_orderings_are_seeded_and_the_first_is_the_corpus_order(specs):
    a, b = compare.orderings(specs, 4), compare.orderings(specs, 4)
    assert [s["id"] for s in a[0]] == list(SEEDS)
    assert [[s["id"] for s in o] for o in a] == [[s["id"] for s in o] for o in b]


def test_two_runs_of_the_same_corpus_reproduce_the_artifact(specs, result):
    with compare._env(BRE_BOB_TRANSPORT="replay", BRE_TAU="0.10", BRE_MAX_ATTEMPTS=None):
        again = compare.compare(specs, n_orderings=1)
    a = compare.stable_view({"result": result})
    b = compare.stable_view({"result": again})
    assert a == b  # every outcome, count and token figure; only wall times differ


def test_markdown_report_states_its_limits(result):
    md = compare.render_markdown({
        "slice": "test", "generated_at": "now", "corpus_sha256": "0" * 64, "corpus_size": 3, "orderings": 1,
        "tau": 0.1, "tau_source": "test", "bob_mode": "replay", "result": result, "look_alikes_in_corpus": 1})
    assert "## Limits" in md and "NOMINAL" in md and "look-alike" in md.lower()
