"""Close thread 0001#8: does ownership asymmetry exist in real repository history?

The premise the ASMOS routing story rests on. ASMOS found asymmetry does NOT emerge
organically in its own constructed corpus, so for BRE it is an assumption until
measured. ADR-0001 records it as a risk to test before stage S8 is built on it.

Method
    claim events   BRE's own connectors/git.py -- a merged commit is a verified
                   claim by its author on the topics its files touch.
    metrics        asmos.e6.asymmetry, UNMODIFIED, imported from the ASMOS checkout.
                   Using the reference implementation is the point: the measurement
                   must not be something BRE invented to flatter itself.
    criterion      ASMOS's own pre-registered bar -- OCI >= 0.70 AND p < 0.001
                   against an agent-label permutation null (B=1000, seed=42).

Each repository is measured twice: with BRE's identity resolution and without it
(raw author name as agent id, which is what the upstream prototype does). The gap
between the two is itself a finding.

    venv/Scripts/python.exe scripts/measure_asymmetry.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

ASMOS_SRC = Path("C:/Users/csdee/PESU/CDSAML/ASMOS/src")

from connectors.git import GitConnector  # noqa: E402

CAPSTONE = (
    "C:/Users/csdee/PESU/capstone/"
    "An-Intelligent-Dental-Assisting-System-for-Dentists-in-Cavity-and-Periodontal-Disease-Detection"
)

TARGETS = [
    ("ASMOS", "C:/Users/csdee/PESU/CDSAML/ASMOS", "4 contributors, 226 commits"),
    ("Dental", CAPSTONE, "2 contributors, 249 commits"),
    ("PAY", "C:/Users/csdee/PESU/PAY", "1 contributor -- negative control"),
    ("BRE", str(REPO_ROOT), "this repo, very short history"),
]


def load_metrics():
    if not ASMOS_SRC.exists():
        raise SystemExit(f"ASMOS checkout not found at {ASMOS_SRC}")
    sys.path.insert(0, str(ASMOS_SRC))
    from asmos.e6.asymmetry import compute_asymmetry_report  # noqa: E402

    return compute_asymmetry_report


def measure(compute, path: str, *, normalized: bool) -> dict:
    try:
        events = GitConnector(path).claim_events(normalize_identities=normalized)
    except Exception as exc:  # noqa: BLE001 -- one bad repo must not kill the sweep
        return {"error": f"{type(exc).__name__}: {exc}"}
    if not events:
        return {"error": "no claim events -- no commit touched a recognised topic"}
    report = compute([e.as_dict() for e in events], {})
    report["n_events"] = len(events)
    report["n_refutations"] = sum(1 for e in events if e.kind == "revert")
    return report


def summarize(label: str, r: dict) -> str:
    if "error" in r:
        return f"  {label:<12} ERROR: {r['error']}"
    null = r["permutation_null"]
    return (
        f"  {label:<12} OCI {r['oci']['oci']:.3f}  p {null['p_value']:.4f}  "
        f"z {null['z_score']:>6.2f}  null {null['null_mean']:.3f}  "
        f"agents {r['n_agents']:>2}  topics {r['n_topics']:>3}  "
        f"claims {r['n_verified_claims']:>4}  {r['pilot_decision']}"
    )


def main() -> int:
    compute = load_metrics()
    print("=" * 100)
    print("OWNERSHIP ASYMMETRY IN REAL REPOSITORIES -- thread 0001#8")
    print("metrics: asmos.e6.asymmetry (unmodified)   criterion: OCI >= 0.70 and p < 0.001")
    print("=" * 100)

    results = {}
    for name, path, note in TARGETS:
        print(f"\n{name}  ({note})")
        norm = measure(compute, path, normalized=True)
        raw = measure(compute, path, normalized=False)
        print(summarize("normalized", norm))
        print(summarize("raw names", raw))
        results[name] = {"path": path, "note": note, "normalized": norm, "raw": raw}

        if "error" not in norm:
            if norm.get("n_refutations", 0) == 0:
                print("  -> NO refutation events: this history contains no git reverts")
            if "error" not in raw:
                delta = norm["oci"]["oci"] - raw["oci"]["oci"]
                if abs(delta) > 0.001:
                    word = "UNDERSTATES" if delta > 0 else "overstates"
                    print(
                        f"  -> raw author names {word} concentration by {abs(delta):.3f} OCI "
                        f"({raw['n_agents']} apparent agents vs {norm['n_agents']} real)"
                    )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = REPO_ROOT / "docs" / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = out_dir / f"asymmetry_{stamp}.json"
    artifact.write_text(
        json.dumps(
            {
                "measured_at": datetime.now(timezone.utc).isoformat(),
                "thread": "0001#8",
                "metrics_source": "asmos.e6.asymmetry (unmodified)",
                "criterion": {"oci_min": 0.70, "p_max": 0.001},
                "results": results,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nartifact: {artifact.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
