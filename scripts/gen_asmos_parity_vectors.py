#!/usr/bin/env python
"""Generate the ASMOS parity vector table from the REAL ASMOS source.

`asmos_bridge` re-implements ASMOS's math (ADR-0001). "Re-implemented faithfully" must be a
test, not a claim, so this script loads ASMOS's own `trust.py` / `reputation.py` /
`routing_decision` straight from the research repository (they are stdlib-pure, so no
`pip install asmos`, no chromadb, no torch) and records what they return on a grid of inputs.
`tests/unit/test_asmos_parity.py` then asserts the bridge returns the same numbers.

    python scripts/gen_asmos_parity_vectors.py [--asmos C:/path/to/ASMOS]

Re-run it when the ASMOS repo changes; a diff in the committed vectors IS the drift alarm.
"""

from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_ASMOS = Path(r"C:\Users\csdee\PESU\CDSAML\ASMOS")
OUT = Path(__file__).resolve().parents[1] / "tests" / "unit" / "asmos_parity_vectors.json"


def load(module_path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, module_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def git_sha(repo: Path) -> str:
    try:
        return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asmos", type=Path, default=DEFAULT_ASMOS)
    args = ap.parse_args()

    src = args.asmos / "src" / "asmos" / "ownership"
    trust_mod = load(src / "trust.py", "_asmos_trust")
    rep_mod = load(src / "reputation.py", "_asmos_reputation")

    vectors: dict = {"trust": [], "ownership": [], "routing_score": [], "routing_decision": [], "reputation": []}

    for vc, vt in itertools.product([0, 1, 2, 5, 10, 50], [0, 1, 2, 5, 10, 50, 200]):
        if vc <= vt:
            vectors["trust"].append({"vc": vc, "vt": vt, "expected": trust_mod.trust(vc, vt)})
    for de, cs in itertools.product([0.0, 0.3, 0.7, 1.0], [0.0, 0.25, 0.5, 1.0]):
        vectors["ownership"].append({"expertise": de, "share": cs, "expected": trust_mod.ownership_score(de, cs)})
    for sim, own in itertools.product([0.0, 0.2, 0.5, 0.9, 1.0], [0.0, 0.42, 0.7, 1.0]):
        vectors["routing_score"].append({"sim": sim, "ownership": own, "expected": trust_mod.routing_score(sim, own)})
    for owners, tau, k in [
        ([], 0.35, 2),
        ([("a", 0.2)], 0.35, 2),
        ([("a", 0.35)], 0.35, 2),
        ([("a", 0.9), ("b", 0.5), ("c", 0.4)], 0.35, 2),
        ([("a", 0.9), ("b", 0.5), ("c", 0.4)], 0.6, 1),
        ([("x", 0.41), ("y", 0.41)], 0.41, 2),
    ]:
        vectors["routing_decision"].append({
            "owners": owners, "tau": tau, "k": k,
            "expected": _jsonable(trust_mod.routing_decision(owners, tau, k)),
        })
    for cls, status in itertools.product(["A", "B", "C", "a", "X"], ["verified", "refuted", "pending", "abandoned"]):
        upd = rep_mod.reputation_update(cls, status)
        vectors["reputation"].append({"claim_class": cls, "status": status,
                                      "expected": [upd.verified_correct_delta, upd.verified_total_delta]})

    payload = {
        "provenance": {
            "source": "ASMOS src/asmos/ownership/{trust,reputation}.py, loaded directly (no install)",
            "asmos_path": str(args.asmos),
            "asmos_git_sha": git_sha(args.asmos),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "note": "Regenerate with scripts/gen_asmos_parity_vectors.py; a diff here is the drift alarm.",
        },
        "constants": {"alpha": 7, "beta": 3},
        "vectors": vectors,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    n = sum(len(v) for v in vectors.values())
    print(f"wrote {n} vectors to {OUT} (ASMOS @ {payload['provenance']['asmos_git_sha'][:10]})")
    return 0


def _jsonable(decision: dict) -> dict:
    return {**decision, "owners": [list(o) for o in decision["owners"]]}


if __name__ == "__main__":
    raise SystemExit(main())
