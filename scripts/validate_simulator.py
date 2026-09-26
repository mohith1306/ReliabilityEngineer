#!/usr/bin/env python
"""Validate the routing simulator against the measured end-to-end comparison runs.

    python scripts/validate_simulator.py

`asmos_bridge/routing/simulate.py` is what tau is tuned on. It is only trustworthy if it reproduces what the real loop
actually did, so this re-simulates EVERY committed `comparison_*.json` ordering at that run's own tau and compares the
(memory-served, memory-refuted) counts with what the harness measured. The result is stamped as
`docs/artifacts/simulator_validation_<stamp>.json` and printed.

Kept separate from the tuning artifacts on purpose: a stamped artifact must not cite files that later change, and this one is
regenerated from whatever comparison artifacts currently exist.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from asmos_bridge.routing.simulate import Item, simulate  # noqa: E402
from reliability.evaluation.run import corpus_digest, load_corpus  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from tune_tau import collect_signatures, nominal_costs  # noqa: E402

ART = ROOT / "docs" / "artifacts"
STAMPED = re.compile(r"comparison_(?P<slice>.+)_\d{8}T\d{6}Z\.json$")


def main() -> int:
    specs_all = load_corpus(ROOT / "tests" / "e2e" / "corpus")
    sigs = collect_signatures(specs_all)
    items = {s["id"]: Item(s["id"], s["topic"], s["repo"], tuple(sigs[s["id"]])) for s in specs_all}
    save, waste = nominal_costs()

    rows = []
    for path in sorted(ART.glob("comparison_*.json")):
        if not STAMPED.search(path.name):
            continue
        art = json.loads(path.read_text(encoding="utf-8"))
        for run in art["result"]["runs"]:
            order = run["order"]
            if not set(order) <= set(items):
                continue
            measured = run["arms"]["bre"]["summary"]
            sim = simulate([items[i] for i in order], art["tau"], save=save, waste=waste)
            rows.append({
                "artifact": path.name, "slice": art.get("slice"), "ordering": run["ordering"], "tau": art["tau"],
                "measured": {"served": measured["memory_diagnoses"], "refuted": measured["memory_refuted"]},
                "simulated": {"served": sim.served, "refuted": sim.refuted},
                "agrees": (measured["memory_diagnoses"], measured["memory_refuted"]) == (sim.served, sim.refuted),
            })
    agree = sum(r["agrees"] for r in rows)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"simulator_validation_{stamp}.json"
    payload = {
        "artifact": name, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "corpus_sha256": corpus_digest(ROOT / "tests" / "e2e" / "corpus"), "agree": agree, "of": len(rows),
        "meaning": "the simulator reproduces the measured (memory-served, memory-refuted) counts of each end-to-end comparison run",
        "runs": rows,
    }
    for old in ART.glob("simulator_validation_*.json"):
        old.unlink()
    (ART / name).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"simulator vs measured end-to-end runs: {agree} of {len(rows)} orderings agree exactly")
    for r in rows:
        if not r["agrees"]:
            print("  DISAGREES:", r)
    print("artifact:", ART / name)
    return 0 if agree == len(rows) and rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
