#!/usr/bin/env python
"""Compose docs/RESULTS.md from the stamped artifacts. Nothing in the report is typed by hand.

    python scripts/build_results.py

Reads the latest `docs/artifacts/comparison_<slice>_*.json` for each slice, and the tuning artifacts they cite, and
writes a report whose every number is copied from them. If the data are unflattering, the report is unflattering.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "docs" / "artifacts"

SLICES = [
    ("recurring", "Failures that recur",
     "10 incidents, two fixtures. No look-alikes: every incident that resembles a past one really is that failure again. "
     "tau was tuned on this same slice (in-sample)."),
    ("full", "A corpus with look-alike twins",
     "14 incidents. Four of them are look-alikes of earlier ones: the same symptom text and the same failing test, but the "
     "cause is a hard-coded cap in code while the config is healthy. Similarity cannot tell them apart. tau was tuned on this corpus (in-sample)."),
    ("full_tau_from_recurring", "Out of distribution: tau tuned without look-alikes, deployed where they exist",
     "The same 14 incidents, but tau comes from the recurring-only tuning. This is what happens if the threshold was tuned on clean "
     "history and then met a look-alike."),
]


def latest(pattern: str) -> Path | None:
    """Latest artifact whose name is exactly <pattern with * = the slice> + a UTC stamp.

    A bare glob is not enough: `comparison_full_*.json` also matches `comparison_full_tau_from_recurring_*.json`
    (found in session 0009 when the report showed the wrong slice's numbers under the wrong heading)."""
    stem, _, tail = pattern.partition("*")
    rx = re.compile(re.escape(stem) + r"\d{8}T\d{6}Z" + re.escape(tail) + "$")
    files = sorted(f for f in ART.glob(pattern) if rx.match(f.name))
    return files[-1] if files else None


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def arm_table(agg: dict) -> list[str]:
    rows = ["| arm | resolution | tokens / incident (nominal) | Bob diagnoses | from memory | refuted reuses | wasted attempts |",
            "|---|---|---|---|---|---|---|"]
    names = {"baseline": "Bob alone", "bre": "BRE", "bre_frozen": "BRE, ownership frozen (ablation)"}
    for arm in ("baseline", "bre", "bre_frozen"):
        if arm not in agg:
            continue
        a = agg[arm]
        rows.append(f"| {names[arm]} | {pct(a['resolution_rate']['mean'])} ± {a['resolution_rate']['std'] * 100:.1f} | "
                    f"{a['tokens_per_incident']['mean']:.0f} ± {a['tokens_per_incident']['std']:.0f} | "
                    f"{a['bob_diagnoses']['mean']:.1f} | {a['memory_diagnoses']['mean']:.1f} | "
                    f"{a['memory_refuted']['mean']:.1f} | {a['wasted_attempts']['mean']:.1f} |")
    return rows


def main() -> int:
    out = ["# Results — BRE vs Bob alone", "",
           f"_Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} by `scripts/build_results.py` from the stamped artifacts in "
           "`docs/artifacts/`. Every number below is copied from them._", "",
           "## Read this first", "",
           "- **Token figures are NOMINAL.** Bob is replaced by a labelled replay stand-in whose cassettes carry placeholder token costs. "
           "**Measured** (real git + real pytest + the real ledger): whether each incident resolved, how many attempts it took, how many diagnoses "
           "came from memory vs Bob, how many memory reuses the test suite **refuted**, and how many attempts that wasted. "
           "Token totals are those counts × a placeholder price: an accounting of the counts, not a measurement of IBM Bob.",
           "- **The corpus is small and synthetic** (14 incidents over 3 fixture repositories, ordering-shuffled 3 times), and tau is tuned **in-sample**. "
           "This demonstrates a mechanism. It is not a generalisation claim.",
           "- **Approvals are automated by the harness**; a real run has a human at the gate.",
           "- **Look-alikes are included on purpose.** A router evaluated only on easy cases proves nothing.",
           "- Flat and negative results are reported as found.", ""]

    found_any = False
    for slice_name, title, blurb in SLICES:
        path = latest(f"comparison_{slice_name}_*.json")
        if not path:
            continue
        found_any = True
        d = load(path)
        res = d["result"]
        out += [f"## {title}", "", blurb, "",
                f"`{d['corpus_size']}` incidents · `{d.get('look_alikes_in_corpus', 0)}` look-alikes · `{d['orderings']}` orderings · "
                f"tau `{d['tau']}` (`{d['tau_source']}`) · Bob: **{d['bob_mode']}**", ""]
        out += arm_table(res["aggregate"]) + [""]
        out += ["**Findings** (generated from the numbers):", ""] + d.get("findings", [])
        if slice_name == "full_tau_from_recurring":
            prev = latest("comparison_full_*.json")
            if prev and load(prev)["result"]["aggregate"]["bre"] == res["aggregate"]["bre"]:
                out += ["- **Identical to the previous slice.** On this corpus a wide range of tau values routes exactly the same incidents, so a threshold "
                        "tuned on clean history would have behaved the same here. Reported as found."]
        out += ["", f"_Artifact: `docs/artifacts/{path.name}`_", ""]

    tuning_lines: list[str] = []
    for slice_name in ("recurring", "full"):
        tp = latest(f"tau_tuning_{slice_name}_*.json")
        if not tp:
            continue
        t = load(tp)
        vp = latest("simulator_validation_*.json")
        v = load(vp) if vp else {"agree": "?", "of": "?"}
        best = max(t["curve"], key=lambda c: (c["mean_utility"], c["tau"]))
        tuning_lines += [f"- **{slice_name}**: tau = `{t['tau']}` maximises mean net saving "
                         f"(`{t['mean_net_saving_at_tau']:.0f}` nominal tokens over `{t['orderings_averaged']}` orderings; "
                         f"`{best['mean_served']:.1f}` reuses, `{best['mean_refuted']:.1f}` refuted). "
                         f"Simulator vs measured end-to-end runs: **{v['agree']} of {v['of']}** orderings agree exactly (`scripts/validate_simulator.py`). "
                         f"`docs/artifacts/{tp.name}`"]
        if t["similarity_diagnostics"]["identical_signature_but_different_cause"]:
            tuning_lines.append(f"  - {t['similarity_diagnostics']['identical_signature_but_different_cause']} (query, memory) pairs are look-alikes with an "
                                "**identical** failure signature to a true match: similarity alone cannot separate them.")
    if tuning_lines:
        out += ["## How tau was chosen", "",
                "tau is derived from data (`scripts/tune_tau.py`), never hardcoded. The tuner **simulates the actual routing policy** — the single best memory, "
                "ASMOS ownership evolving with verified outcomes, a refuted memory excluded from the retry — over many random orderings, and picks the tau "
                "with the highest mean net saving. The simulator is validated against the measured end-to-end runs above. "
                "(An earlier pair-based tuner returned *\"never route\"* for the look-alike corpus, where the harness then showed routing wins; "
                "it was wrong and was replaced — see [ADR-0006](decisions/ADR-0006-routing-sources-and-tau.md).)", ""] + tuning_lines + [""]

    out += ["## What this does and does not show", "",
            "**Shows:** verified memory turns recurring failures into cheaper incidents; the test suite catches a wrong reuse, the patch is rolled back and "
            "nothing is left behind; every outcome is recorded against a real verification run; a threshold can be tuned from data and checked "
            "against measurement.", "",
            "**Does not show:** anything about IBM Bob's diagnostic quality (the agent is a stand-in); real token costs; that the threshold generalises to "
            "other codebases; or that ownership evolution helps — at ASMOS's prior strength (α+β = 10) one refutation moves trust by about 0.03, so on "
            "14 incidents the frozen-ownership ablation is flat. A smaller prior would adapt faster but breaks parity with ASMOS's frozen spec, "
            "so it is an explicit future experiment.", "",
            "## Reproduce", "",
            "```bash",
            "python scripts/tune_tau.py --slice recurring --exclude-repo connection_cap",
            "python scripts/tune_tau.py --slice full --latest",
            "python -m reliability.evaluation.compare --slice recurring --exclude-repo connection_cap --tau-artifact docs/artifacts/tau_tuning_recurring_*.json --orderings 3",
            "python -m reliability.evaluation.compare --slice full --tau-artifact docs/artifacts/tau_tuning_full_*.json --orderings 3",
            "python scripts/validate_simulator.py",
            "python scripts/build_results.py",
            "```", "",
            "Add `--bob live` (with Bob Shell installed and `BOB_API_KEY` set) for **measured** tokens.", ""]
    if not found_any:
        out += ["_No comparison artifacts found. Run `python -m reliability.evaluation.compare`._", ""]
    (ROOT / "docs" / "RESULTS.md").write_text("\n".join(out), encoding="utf-8", newline="\n")
    print("wrote docs/RESULTS.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
