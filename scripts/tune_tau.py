#!/usr/bin/env python
"""Tune tau on the corpus and stamp the run (S8 exit criterion: tau is derived from data, never hardcoded).

    python scripts/tune_tau.py [--slice full] [--exclude-repo connection_cap] [--latest]

Method (asmos_bridge/routing/simulate.py): build every corpus incident's real failure signature from an actual
investigation, then SIMULATE BRE's sequential routing policy -- single best memory, ASMOS ownership evolving as
outcomes accrue, a refuted memory excluded from the retry -- over many random orderings, and choose the tau that
maximises mean net saving:  (correct reuses x save)  -  (refuted reuses x waste).

    save  = a correct reuse skips one Bob diagnosis
    waste = a wrong reuse burns one remediation attempt that is then rolled back

Both are NOMINAL token costs read from the replay cassettes and labelled as such.

Why a simulator and not independent (memory, incident) pairs: an earlier version tuned on pairs and reported "never
route" for a corpus where the end-to-end harness then showed routing WINS. The router consults the single best match,
sequentially, with evolving ownership -- pairs are the wrong model. The simulator is therefore validated against the
measured harness artifacts by scripts/validate_simulator.py.

The pair-based similarity diagnostics are kept in the artifact: they show WHY similarity alone cannot separate
look-alikes (same failing test, different cause), which is what verification exists to catch.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.api.database import IncidentDB  # noqa: E402
from apps.api.services.investigation_service import run_investigation  # noqa: E402
from asmos_bridge.memory.signature import failure_signature  # noqa: E402
from asmos_bridge.memory.store import cosine  # noqa: E402
from asmos_bridge.ownership.trust import ownership_score, trust  # noqa: E402
from asmos_bridge.routing.simulate import Item, orderings, simulate, tune_by_simulation  # noqa: E402
from bob.replay import load_cassettes  # noqa: E402
from reliability.evaluation.compare import _new_session  # noqa: E402
from reliability.evaluation.fixtures import build_fixture_repo  # noqa: E402
from reliability.evaluation.run import corpus_digest, load_corpus  # noqa: E402
from reliability.orchestration.lifecycle import latest_evidence, to_model  # noqa: E402


def collect_signatures(specs: list[dict]) -> dict[str, list[str]]:
    engine, db = _new_session()
    sigs: dict[str, list[str]] = {}
    try:
        with tempfile.TemporaryDirectory(prefix="bre-tau-") as tmp:
            for spec in specs:
                repo = build_fixture_repo(spec["repo"], Path(tmp) / spec["id"])
                meta = dict(spec["incident"].get("metadata", {}))
                meta.update({"repo_path": str(repo), "topic": spec["topic"]})
                row = IncidentDB(
                    id=f"tau_{spec['id']}", repository=spec["repo"], type=spec["incident"].get("type", "test_failure"),
                    severity=spec["incident"].get("severity", "medium"), status="DETECTED",
                    description=spec["incident"]["description"], metadata_json=meta)
                db.add(row)
                db.commit()
                run_investigation(db, row, repo_path=str(repo))
                db.commit()
                sigs[spec["id"]] = failure_signature(to_model(row), latest_evidence(db, row.id))
    finally:
        db.close()
        engine.dispose()
    return sigs


def nominal_costs() -> tuple[float, float]:
    cassettes = load_cassettes()
    return (statistics.fmean(c.diagnosis.get("usage_tokens", 0) for c in cassettes),
            statistics.fmean(c.remediation.get("usage_tokens", 0) for c in cassettes))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(ROOT / "tests" / "e2e" / "corpus"))
    ap.add_argument("--out", default=str(ROOT / "docs" / "artifacts"))
    ap.add_argument("--exclude-repo", action="append", default=[], help="drop a fixture from the corpus (slices)")
    ap.add_argument("--slice", default="full", help="label; the artifact is tau_tuning_<slice>_<stamp>.json")
    ap.add_argument("--orderings", type=int, default=50, help="random orderings to average over")
    ap.add_argument("--latest", action="store_true", help="also write tau_tuning_latest.json (what the router loads)")
    args = ap.parse_args()

    specs = [s for s in load_corpus(args.corpus) if s["repo"] not in args.exclude_repo]
    sigs = collect_signatures(specs)
    items = [Item(s["id"], s["topic"], s["repo"], tuple(sigs[s["id"]])) for s in specs]
    save, waste = nominal_costs()
    corpus_sha = corpus_digest(args.corpus)

    tuned = tune_by_simulation(items, save=save, waste=waste, n_orderings=args.orderings)
    cold = ownership_score(trust(0, 0), 0.0)

    # diagnostics: how separable are true matches from look-alikes by similarity alone?
    pos, neg = [], []
    for q in items:
        for m in items:
            if q.id != m.id and q.topic == m.topic:
                (pos if q.group == m.group else neg).append(round(cosine(q.signature, m.signature), 4))
    lookalikes = sum(1 for q in items for m in items if q.id != m.id and q.topic == m.topic
                     and q.group != m.group and cosine(q.signature, m.signature) >= 0.999)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"tau_tuning_{args.slice}_{stamp}.json"
    artifact = {
        "artifact": name, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "method": "simulated_sequential_routing_max_mean_net_saving", "tau": tuned.tau,
        "slice": args.slice, "excluded_repos": args.exclude_repo, "incidents": len(specs),
        "orderings_averaged": tuned.n_orderings, "corpus": str(args.corpus), "corpus_sha256": corpus_sha,
        "cold_start_ownership": cold, "mean_net_saving_at_tau": tuned.mean_utility,
        "note": tuned.note,
        "cost_units": {"save": round(save, 1), "waste": round(waste, 1),
                       "note": "NOMINAL tokens from bob/cassettes/*.json (usage_is_simulated); not a Bob measurement"},
        "similarity_diagnostics": {
            "same_scenario_pairs": {"n": len(pos), "min": min(pos or [0]), "median": statistics.median(pos or [0]), "max": max(pos or [0])},
            "different_scenario_pairs": {"n": len(neg), "min": min(neg or [0]), "median": statistics.median(neg or [0]), "max": max(neg or [0])},
            "identical_signature_but_different_cause": lookalikes,
            "reading": ("look-alikes share a failure signature with true matches, so no threshold separates them by similarity; "
                        "verification refutes the wrong ones and the trust update lowers the memory's ownership")
                       if lookalikes else "no identical-signature look-alikes in this slice",
        },
        "curve": tuned.curve,
        "validation": "see docs/artifacts/simulator_validation_*.json (scripts/validate_simulator.py): the simulator is checked against the measured end-to-end runs",
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / name).write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8", newline="\n")
    if args.latest:
        (out / "tau_tuning_latest.json").write_text(
            json.dumps({"tau": tuned.tau, "artifact": name, "corpus_sha256": corpus_sha, "slice": args.slice}, indent=2) + "\n",
            encoding="utf-8", newline="\n")
    print(f"[{args.slice}] tau = {tuned.tau}   mean net saving {tuned.mean_utility:.0f} nominal tokens over {tuned.n_orderings} orderings")
    if tuned.note:
        print("   ", tuned.note)
    print("    curve: " + "  ".join(f"tau {c['tau']}: {c['mean_utility']:+.0f} ({c['mean_served']:.1f} reused, {c['mean_refuted']:.1f} refuted)"
                                     for c in tuned.curve))
    print("    validate the simulator against measured runs: python scripts/validate_simulator.py")
    print("    artifact:", out / name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
