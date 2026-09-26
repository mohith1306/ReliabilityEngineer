"""S8 -- ASMOS ownership routing, on BRE's own ledger.

Exit criteria (docs/stages/STAGES.md):
  * ownership is sourced from OutcomeRecord closures only, never from commit counts
  * ownership updates ONLY on a verification outcome (Invariant 3), asserted in test
  * a routing decision records its components: similarity, ownership, tau, action
  * tau is tuned on the corpus, not hardcoded
  * cold-start and no-owner cases fall back to full investigation rather than misrouting
"""

from __future__ import annotations

import ast
import json
import uuid
from pathlib import Path

import pytest

from apps.api.database import OutcomeRecordDB, VerificationDB, generate_id
from asmos_bridge.memory.store import MemoryNotVerified, MemoryStore, cosine
from asmos_bridge.ownership.ledger import OwnershipTable
from asmos_bridge.ownership.trust import GLOBAL_SEARCH, ROUTE, trust
from asmos_bridge.routing import router as router_mod
from asmos_bridge.routing.router import DEFAULT_TAU, TransactiveRouter, resolve_tau
from asmos_bridge.routing.tuning import tune_tau
from models.diagnosis import Diagnosis
from models.outcome import ClaimClass, OutcomeRecordCreate, OutcomeStatus, PredictionType
from reliability.ledger.record import OutcomeLedger
from reliability.orchestration.loop import DiagnoseResult
from reliability.orchestration.routed import make_routed_diagnoser, routed_diagnoser
from reliability.remediation import git_ops
from reliability.evaluation.fixtures import build_fixture_repo
from tests.support.loop_helpers import Recorder, decide, drive, git, incident, make_loop, records

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("BRE_BOB_TRANSPORT", "replay")
    monkeypatch.setenv("BRE_TAU", "0.30")  # explicit, so these tests do not depend on a tuning artifact
    monkeypatch.delenv("BRE_MAX_ATTEMPTS", raising=False)


# ── ledger scaffolding ────────────────────────────────────────────────────────────────


def run_row(db, incident_id, *, passed=True) -> str:
    row = VerificationDB(id=uuid.uuid4().hex[:12], incident_id=incident_id, remediation_id="r",
                         status="passed" if passed else "failed", levels={})
    db.add(row)
    db.flush()
    return row.id


def record(db, *, predictor="bob-adapter", topic="database", ptype=PredictionType.DIAGNOSIS,
           cls=ClaimClass.B, status="confirmed", run="real", incident_id=None):
    """A ledger record opened and closed the way the engines do, with control over what closed it."""
    incident_id = incident_id or generate_id()
    ledger = OutcomeLedger(db)
    rec = ledger.open(OutcomeRecordCreate(
        incident_id=incident_id, predictor_id=predictor, topic=topic, prediction_type=ptype,
        claim_class=cls, confidence=0.8, components={"x": 1}))
    if status == "pending":
        return rec
    if status == "abandoned":
        ledger.abandon_pending(incident_id, closed_by="loop")
        return rec
    run_id = {"real": lambda: run_row(db, incident_id, passed=status == "confirmed"),
              "eval": lambda: "eval:20260927"}[run]()
    ledger.close(rec.id, OutcomeStatus(status), closed_by="verification-engine", verification_run_id=run_id)
    return rec


# ── ownership comes from verification closures and nothing else ─────────────────────────


def test_only_verification_backed_diagnosis_closures_move_reputation(db):
    record(db, status="confirmed")                          # +0.5 / +0.5  (class B = half update)
    record(db, status="refuted")                            # 0   / +0.5
    record(db, status="confirmed", run="eval")              # closed by the harness, not a verification run
    record(db, status="pending")                            # nobody has tested it
    record(db, status="abandoned")                          # the loop gave up: untested
    record(db, status="confirmed", cls=ClaimClass.C)        # speculation never moves reputation
    record(db, status="confirmed", ptype=PredictionType.RISK_LEVEL)  # not a diagnosis
    s = OwnershipTable.from_ledger(db).standing("bob", "database")
    assert (s.verified_correct, s.verified_total) == (0.5, 1.0)
    assert s.trust == trust(0.5, 1.0)


def test_reputation_moves_on_verification_never_on_generation(db):
    """Invariant 3, as a before/after: producing a prediction changes nothing; closing it does."""
    inc = generate_id()
    ledger = OutcomeLedger(db)
    rec = ledger.open(OutcomeRecordCreate(
        incident_id=inc, predictor_id="bob-adapter", topic="database", prediction_type=PredictionType.DIAGNOSIS,
        claim_class=ClaimClass.B, confidence=0.9, components={"x": 1}))
    assert OwnershipTable.from_ledger(db).standing("bob", "database").verified_total == 0  # generated, not verified
    ledger.close(rec.id, OutcomeStatus.CONFIRMED, closed_by="verification-engine",
                 verification_run_id=run_row(db, inc))
    after = OwnershipTable.from_ledger(db).standing("bob", "database")
    assert (after.verified_correct, after.verified_total) == (0.5, 0.5) and after.trust > 0.7


def test_ownership_never_reads_git_history():
    """Session 0008 measured git-derived ownership as indistinguishable from chance at small N, and
    BRE's sources (Bob, memory) appear in no commit history. No bridge module may import git."""
    bad = []
    for path in (REPO_ROOT / "asmos_bridge").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for n in names:
                if n.startswith("connectors") or n.split(".")[0] in ("git", "subprocess"):
                    bad.append(f"{path.name}: {n}")
    assert not bad, bad


def test_contribution_share_is_relative_to_every_source_in_the_topic(db):
    record(db, predictor="bob-adapter")
    record(db, predictor="bob-adapter")
    record(db, predictor="memory")
    t = OwnershipTable.from_ledger(db)
    assert round(t.standing("bob", "database").contribution_share, 4) == round(1.0 / 1.5, 4)
    assert round(t.standing("memory", "database").contribution_share, 4) == round(0.5 / 1.5, 4)
    assert t.standing("bob", "auth").contribution_share == 0.0  # a different topic is untouched


def test_replay_and_bob_adapter_predictions_count_as_the_same_source(db):
    record(db, predictor="bob-adapter")
    record(db, predictor="replay-bob")
    assert OwnershipTable.from_ledger(db).standing("bob", "database").verified_total == 1.0


# ── memory only holds what was verified ─────────────────────────────────────────────────


def put(db, inc, run, **kw):
    return MemoryStore(db).put_verified(
        topic=kw.get("topic", "database"), root_cause=kw.get("root_cause", "pool_size lowered"),
        affected_components=kw.get("components", ["config/app.yaml"]), assumptions=["a"],
        keywords=kw.get("keywords", ["connection", "pool", "exhaustion"]),
        source_incident_id=inc, source_predictor="bob", verification_run_id=run, confidence=0.86)


def test_memory_refuses_anything_not_backed_by_a_passed_run(db):
    inc = generate_id()
    with pytest.raises(MemoryNotVerified, match="missing"):
        put(db, inc, "no-such-run")
    with pytest.raises(MemoryNotVerified, match="failed"):
        put(db, inc, run_row(db, inc, passed=False))
    with pytest.raises(MemoryNotVerified, match="different incident"):
        put(db, inc, run_row(db, "someone-else"))
    assert MemoryStore(db).all() == []


def test_corrections_supersede_and_never_overwrite(db):
    a, b = generate_id(), generate_id()
    first = put(db, a, run_row(db, a))
    second = put(db, b, run_row(db, b), root_cause="pool_size lowered again")
    active = MemoryStore(db).active("database")
    assert [m.id for m in active] == [second.id]
    old = MemoryStore(db).get(first.id)
    assert old.status == "superseded" and old.superseded_by == second.id  # the old record still exists


def test_different_components_are_kept_side_by_side(db):
    a, b = generate_id(), generate_id()
    put(db, a, run_row(db, a), components=["config/app.yaml"])
    put(db, b, run_row(db, b), components=["dbpool.py"])
    assert len(MemoryStore(db).active("database")) == 2


# ── the router ──────────────────────────────────────────────────────────────────────────


KW = ["connection", "pool", "exhaustion", "database", "connector"]


def test_cold_start_falls_back_to_full_investigation(db):
    d = TransactiveRouter(db).route(topic="database", keywords=KW)
    assert (d.action, d.routed_to) == (GLOBAL_SEARCH, "bob")
    assert "cold start" in d.reason and d.memory is None
    assert d.components["ownership"]["trust"] == 0.7  # the prior, visible, not hidden


def test_a_verified_memory_earns_a_route_and_the_decision_records_its_components(db):
    inc = generate_id()
    m = put(db, inc, run_row(db, inc), keywords=KW)
    d = TransactiveRouter(db).route(topic="database", keywords=KW)
    assert (d.action, d.routed_to) == (ROUTE, "memory") and d.memory.id == m.id
    c = d.components
    assert c["similarity"] == 1.0 and c["tau"] == 0.30 and c["tau_source"] == "env:BRE_TAU"
    assert c["ownership"]["trust"] == 0.7 and c["ownership"]["contribution_share"] == 0.0
    assert round(c["ownership"]["ownership"], 4) == 0.42 and round(c["routing_score"], 4) == 0.42
    assert c["candidates"][0]["memory_id"] == m.id and c["action"] == ROUTE


def test_a_dissimilar_incident_falls_back_rather_than_misrouting(db):
    inc = generate_id()
    put(db, inc, run_row(db, inc), keywords=KW)
    d = TransactiveRouter(db).route(topic="database", keywords=["login", "timeout", "session", "token"])
    assert d.action == GLOBAL_SEARCH and "< tau" in d.reason and d.components["similarity"] == 0.0


def test_memory_from_another_topic_is_invisible(db):
    inc = generate_id()
    put(db, inc, run_row(db, inc), topic="auth", keywords=KW)
    assert TransactiveRouter(db).route(topic="database", keywords=KW).action == GLOBAL_SEARCH


def test_a_memory_already_tried_on_this_incident_is_excluded(db):
    inc = generate_id()
    m = put(db, inc, run_row(db, inc), keywords=KW)
    d = TransactiveRouter(db).route(topic="database", keywords=KW, exclude_memory_ids=[m.id])
    assert d.action == GLOBAL_SEARCH and "already tried" in d.reason


def test_ownership_grows_with_verified_reuse_and_shrinks_with_refutation(db):
    def memory_ownership():
        return OwnershipTable.from_ledger(db).standing("memory", "database").ownership

    cold = memory_ownership()
    for _ in range(3):
        record(db, predictor="memory", status="confirmed")
    grown = memory_ownership()
    for _ in range(6):
        record(db, predictor="memory", status="refuted")
    shrunk = memory_ownership()
    assert cold < grown        # earned by verified reuse
    assert shrunk < grown      # lost by refutation -- no retraining, no threshold edit


def test_tau_resolution_order_and_labels(monkeypatch, tmp_path):
    monkeypatch.setenv("BRE_TAU", "0.5")
    assert resolve_tau() == (0.5, "env:BRE_TAU")
    monkeypatch.delenv("BRE_TAU")
    artifact = tmp_path / "tau.json"
    artifact.write_text(json.dumps({"tau": 0.27, "artifact": "tau_x.json"}), encoding="utf-8")
    monkeypatch.setattr(router_mod, "TUNED_TAU_FILE", artifact)
    assert resolve_tau() == (0.27, "tuned:tau_x.json")
    monkeypatch.setattr(router_mod, "TUNED_TAU_FILE", tmp_path / "missing.json")
    assert resolve_tau() == (DEFAULT_TAU, "default:asmos")  # the fallback is labelled, never silent


def test_cosine_is_the_documented_binary_bag_cosine():
    assert cosine(["a", "b"], ["a", "b"]) == 1.0
    assert cosine(["a", "b"], ["c"]) == 0.0
    assert cosine([], ["a"]) == 0.0
    assert round(cosine(["a", "b", "c", "d"], ["a", "b"]), 4) == round(2 / (4 * 2) ** 0.5, 4)


# ── tau is tuned from data ──────────────────────────────────────────────────────────────


def test_tuning_places_tau_between_separable_classes():
    r = tune_tau([(0.38, True), (0.40, True), (0.36, True), (0.08, False), (0.12, False), (0.05, False)])
    assert r.j == 1.0 and (r.fp, r.fn) == (0, 0) and not r.notes
    assert r.tau == pytest.approx(0.24)  # the max-margin midpoint: highest negative 0.12, lowest positive 0.36


def test_tuning_ties_break_toward_the_higher_tau():
    """When two thresholds are equally good, take the stricter one: a wrongly reused diagnosis costs a
    failed attempt, a missed reuse costs only tokens."""
    r = tune_tau([(0.50, True), (0.10, True), (0.30, False), (0.20, False)])
    assert r.tau > 0.3 and (r.tp, r.fp) == (1, 0)  # tau=0.4 (J=0.5, no false reuse) beats tau=0.15 (J=0.0)


def test_tuning_reports_what_similarity_cannot_separate():
    r = tune_tau([(0.40, True), (0.30, True), (0.41, False), (0.10, False)])
    assert r.j < 1.0 and any("cannot reject" in n or "fall back" in n for n in r.notes)


def test_tuning_needs_both_classes():
    with pytest.raises(ValueError):
        tune_tau([(0.4, True), (0.3, True)])


# ── the whole thing, end to end, on real git repositories ─────────────────────────────────


def loop_for(db, repo, *, executor=None, diagnoser=routed_diagnoser):
    return make_loop(db, repo, diagnoser=diagnoser, **({"executor_factory": lambda: executor} if executor else {}))


def diagnosis_sources(db, inc):
    return [(r.predictor_id, r.cost_tokens) for r in records(db, inc) if r.prediction_type == "diagnosis"]


def test_the_second_similar_incident_is_served_from_verified_memory_at_zero_bob_tokens(db, seeded_repo, tmp_path):
    first = incident(db, seeded_repo)
    drive(db, loop_for(db, seeded_repo), first)
    assert first.status == "RESOLVED"
    routing1 = [r for r in records(db, first) if r.prediction_type == "routing"]
    assert routing1[0].prediction_payload["routed_to"] == "bob"  # cold start -> full investigation
    assert diagnosis_sources(db, first) == [("bob-adapter", 4200)]
    [memory] = MemoryStore(db).active("database")               # promoted only after verification passed
    assert memory.source_incident_id == first.id and memory.source_predictor == "bob"

    second_repo = build_fixture_repo("seeded_failure", tmp_path / "second")
    second = incident(db, second_repo)
    drive(db, loop_for(db, second_repo), second)

    assert second.status == "RESOLVED"                           # and it was really fixed and tested
    assert "pool_size: 20" in git(second_repo, "show", f"bre/{second.id}/attempt-1:config/app.yaml")
    routing2 = [r for r in records(db, second) if r.prediction_type == "routing"]
    assert routing2[0].prediction_payload["routed_to"] == "memory"
    assert diagnosis_sources(db, second) == [("memory", 0)]      # zero Bob tokens for the diagnosis
    assert len(MemoryStore(db).active("database")) == 1          # a memory-served answer is not re-consolidated

    # reputation moved because verification confirmed the reuse -- and only for that reason
    table = OwnershipTable.from_ledger(db)
    mem, bob = table.standing("memory", "database"), table.standing("bob", "database")
    assert (mem.verified_correct, mem.verified_total) == (0.5, 0.5) and mem.trust > 0.7 and mem.contribution_share > 0
    assert (bob.verified_correct, bob.verified_total) == (0.5, 0.5)
    assert mem.ownership > 0.42  # the memory earned more ownership than it started with
    # every prediction on both incidents closed by a real run
    for inc in (first, second):
        assert all(r.status == "confirmed" and r.verification_run_id for r in records(db, inc))


def test_memory_reuse_that_fails_verification_is_refuted_excluded_next_time_and_costs_trust(db, seeded_repo, tmp_path):
    first = incident(db, seeded_repo)
    drive(db, loop_for(db, seeded_repo), first)
    before = OwnershipTable.from_ledger(db).standing("memory", "database")

    # A LOOK-ALIKE: same symptom text, healthy config -- but the real bug is a hard-coded cap in code.
    variant = build_fixture_repo("seeded_failure", tmp_path / "variant")
    cfg = variant / "config/app.yaml"
    cfg.write_bytes(cfg.read_bytes().replace(b"pool_size: 2", b"pool_size: 20"))
    pool = variant / "dbpool.py"
    pool.write_bytes(pool.read_bytes().replace(b"        self.size = size", b"        self.size = min(size, 2)"))
    git(variant, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "cap pool at 2 in code")
    assert git_ops.tracked_modifications(variant) == []

    calls = {"n": 0}

    def wrong_then_right(root):
        calls["n"] += 1
        if calls["n"] == 1:   # what the memory suggests: change the config. Plausible, and wrong here.
            c = root / "config/app.yaml"
            c.write_bytes(c.read_bytes().replace(b"pool_size: 20", b"pool_size: 30"))
        else:                 # what a real investigation finds: the cap in the code
            p = root / "dbpool.py"
            p.write_bytes(p.read_bytes().replace(b"min(size, 2)", b"size"))

    ex = Recorder(wrong_then_right)

    def fallback(req):        # the full investigation (Bob) for the attempt the memory lost
        from reliability.ledger.record import open_diagnosis_prediction
        d = Diagnosis(id=f"dx-{generate_id()}", incident_id=req.incident.id, confidence=0.8,
                      root_cause="dbpool.py caps the pool at min(size, 2) regardless of config",
                      affected_components=["dbpool.py"], assumptions=["the cap is unintentional"])
        open_diagnosis_prediction(req.db, incident_id=req.incident.id, predictor_id="bob-adapter",
                                  topic=req.topic, root_cause=d.root_cause, confidence=0.8,
                                  components={"provider": "test"}, attempt_number=req.attempt, cost_tokens=3000)
        return DiagnoseResult(d, "bob")

    second = incident(db, variant)
    drive(db, loop_for(db, variant, executor=ex, diagnoser=make_routed_diagnoser(fallback)), second)

    assert second.status == "RESOLVED" and second.attempt == 2
    by_attempt = {}
    for r in records(db, second):
        by_attempt.setdefault(r.attempt_number, []).append(r)
    d1 = [r for r in by_attempt[1] if r.prediction_type == "diagnosis"][0]
    d2 = [r for r in by_attempt[2] if r.prediction_type == "diagnosis"][0]
    assert (d1.predictor_id, d1.status) == ("memory", "refuted")   # a real, verified negative
    assert (d2.predictor_id, d2.status) == ("bob-adapter", "confirmed")
    r1 = [r for r in by_attempt[1] if r.prediction_type == "routing"][0]
    r2 = [r for r in by_attempt[2] if r.prediction_type == "routing"][0]
    assert (r1.prediction_payload["routed_to"], r2.prediction_payload["routed_to"]) == ("memory", "bob")
    assert "already tried" in r2.components["reason"]              # the loser was not offered again

    after = OwnershipTable.from_ledger(db).standing("memory", "database")
    assert after.verified_total > before.verified_total and after.verified_correct == before.verified_correct
    assert after.trust < before.trust and after.ownership < before.ownership   # refutation cost it standing
    assert len(MemoryStore(db).active("database")) == 2            # the new, different root cause was learned
