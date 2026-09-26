"""Baseline vs BRE over the same corpus, through the real reliability loop. Stage S9.

    python -m reliability.evaluation.compare --corpus tests/e2e/corpus --orderings 3

Three arms run the SAME incidents in the SAME order, each against a fresh database and freshly built
git repositories, through the real loop (investigate -> diagnose -> risk -> approve -> remediate on a
branch -> verify against pytest -> roll back or resolve):

    baseline     Bob alone: every incident gets a full Bob diagnosis. No memory is consulted.
    bre          BRE: verification-gated ownership routing. A verified memory answers when it has earned
                 the right (score >= tau); otherwise Bob. Ownership evolves with every verification.
    bre_frozen   ABLATION: BRE with ownership frozen at its cold-start prior. If BRE's behaviour differs
                 from this, the cause is ownership EVOLUTION and not merely having a memory -- ASMOS's
                 own single-variable ablation, applied here.

WHAT IS MEASURED AND WHAT IS NOT -- this matters more than the numbers:

  MEASURED (real, from git + pytest + the ledger): whether each incident resolved, how many attempts it
  took, how many diagnoses came from memory vs Bob, how many memory reuses were REFUTED by the test suite,
  and how many attempts that wasted.

  NOT MEASURED (nominal): token cost. With Bob replaced by its labelled replay stand-in, tokens are the
  cassettes' placeholder figures, so "tokens" here is `count of Bob calls x a nominal price`. The reuse
  and refutation counts are real; the token totals are an accounting of them, NOT a measurement of
  Bob. Run with `--bob live` (and a Bob API key) for measured tokens.

Every result is reported as found, including a flat or negative one. The corpus deliberately contains
look-alike incidents (same symptom text, different cause) because a router evaluated only on easy cases
proves nothing.

Determinism: orderings are seeded (ordering 0 is the corpus order); `stable_view` strips wall times.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import random
import statistics
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.database import ApprovalDB, Base, IncidentDB, OperatorDB, OutcomeRecordDB, RiskAssessmentDB, generate_id
from asmos_bridge.memory.store import MemoryStore
from asmos_bridge.ownership.ledger import OwnershipTable
from asmos_bridge.routing.router import resolve_tau
from reliability.evaluation.fixtures import build_fixture_repo
from reliability.evaluation.run import corpus_digest, load_corpus
from reliability.orchestration.loop import ReliabilityLoop, bob_diagnoser
from reliability.orchestration.routed import make_routed_diagnoser
from reliability.remediation.allowlist import RepoAllowlist
from reliability.remediation.executors import ReplayExecutor, select_executor
from reliability.verification.test_runner import TestRunner

HARNESS_VERSION = 1
ARMS = ("baseline", "bre", "bre_frozen")
APPROVER = "evaluation-harness (automated approver)"
VOLATILE = frozenset({"generated_at", "wall_ms", "total_wall_ms", "artifact_path", "report_path", "mean_wall_ms"})

COST_NOTE = ("Token figures are NOMINAL when Bob is replayed (bob/cassettes/*.json: usage_is_simulated=true). "
             "Reuse, refutation, attempt and resolution counts are measured; token totals are those counts "
             "times a placeholder price, not a measurement of IBM Bob.")


@contextlib.contextmanager
def _env(**values):
    old = {k: os.environ.get(k) for k in values}
    try:
        for k, v in values.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = str(v)
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _new_session():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return engine, sessionmaker(autocommit=False, autoflush=False, bind=engine)()


def _approve(db, incident_id: str, operator: OperatorDB) -> None:
    level = (db.query(RiskAssessmentDB).filter_by(incident_id=incident_id)
             .order_by(RiskAssessmentDB.created_at.desc()).first().risk_level)
    db.add(ApprovalDB(id=generate_id(), incident_id=incident_id, risk_level=level, decision="APPROVED",
                      operator_id=operator.id, operator_name=operator.name,
                      reason="automated approval by the evaluation harness (not a human)",
                      created_at=datetime.now(timezone.utc).replace(tzinfo=None)))
    db.commit()


def _diagnoser(arm: str):
    if arm == "baseline":
        return bob_diagnoser
    return make_routed_diagnoser(frozen_ownership=(arm == "bre_frozen"))


def run_incident(db, loop: ReliabilityLoop, spec: dict, workdir: Path, arm: str, operator: OperatorDB) -> dict:
    repo = build_fixture_repo(spec["repo"], workdir / spec["id"])
    meta = dict(spec["incident"].get("metadata", {}))
    meta.update({"repo_path": str(repo), "topic": spec["topic"]})
    row = IncidentDB(
        id=f"{arm}_{spec['id']}", repository=spec["repo"], branch=spec["incident"].get("branch", "main"),
        type=spec["incident"].get("type", "test_failure"), severity=spec["incident"].get("severity", "medium"),
        status="DETECTED", description=spec["incident"]["description"], metadata_json=meta,
    )
    db.add(row)
    db.commit()

    started = time.perf_counter()
    for _ in range(40):  # bounded: a runaway loop fails the run instead of hanging it
        res = loop.advance(row.id)
        db.refresh(row)
        if res.blocked_on == "approval":
            _approve(db, row.id, operator)
            continue
        break
    wall_ms = (time.perf_counter() - started) * 1000.0

    recs = db.query(OutcomeRecordDB).filter_by(incident_id=row.id).all()
    diag = [r for r in recs if r.prediction_type == "diagnosis"]
    rem = [r for r in recs if r.prediction_type == "remediation_plan"]
    final_verified = [r for r in diag if r.status == "confirmed"]
    memory_diag = [r for r in diag if r.predictor_id == "memory"]
    return {
        "id": spec["id"], "repo": spec["repo"], "topic": spec["topic"], "outcome": row.status,
        "resolved": row.status == "RESOLVED", "attempts": row.attempt or 1,
        "served_from_memory": bool(final_verified and final_verified[-1].predictor_id == "memory"),
        "bob_diagnoses": len(diag) - len(memory_diag), "memory_diagnoses": len(memory_diag),
        "memory_refuted": sum(1 for r in memory_diag if r.status == "refuted"),
        "diagnosis_tokens": sum(r.cost_tokens for r in diag), "remediation_tokens": sum(r.cost_tokens for r in rem),
        "wall_ms": round(wall_ms, 1),
    }


def summarise(results: list[dict]) -> dict:
    n = len(results)
    tok = sum(r["diagnosis_tokens"] + r["remediation_tokens"] for r in results)
    return {
        "incidents": n,
        "resolved": sum(r["resolved"] for r in results),
        "resolution_rate": round(sum(r["resolved"] for r in results) / n, 4) if n else 0.0,
        "not_resolved": [r["id"] for r in results if not r["resolved"]],
        "mean_attempts": round(sum(r["attempts"] for r in results) / n, 4) if n else 0.0,
        "wasted_attempts": sum(r["attempts"] - 1 for r in results),
        "bob_diagnoses": sum(r["bob_diagnoses"] for r in results),
        "memory_diagnoses": sum(r["memory_diagnoses"] for r in results),
        "served_from_memory": sum(r["served_from_memory"] for r in results),
        "memory_refuted": sum(r["memory_refuted"] for r in results),
        "diagnosis_tokens": sum(r["diagnosis_tokens"] for r in results),
        "remediation_tokens": sum(r["remediation_tokens"] for r in results),
        "total_tokens": tok,
        "tokens_per_incident": round(tok / n, 2) if n else 0.0,
        "total_wall_ms": round(sum(r["wall_ms"] for r in results), 1),
    }


def run_arm(specs: list[dict], arm: str, *, executor_factory: Callable = ReplayExecutor,
            runner: Optional[TestRunner] = None) -> dict:
    engine, db = _new_session()
    operator = OperatorDB(id=generate_id(), name=APPROVER, api_key_hash=hashlib.sha256(arm.encode()).hexdigest())
    db.add(operator)
    db.commit()
    try:
        with tempfile.TemporaryDirectory(prefix=f"bre-cmp-{arm}-") as tmp:
            workdir = Path(tmp)
            loop = ReliabilityLoop(db, diagnoser=_diagnoser(arm), executor_factory=executor_factory,
                                   allowlist=RepoAllowlist([workdir]), runner=runner or TestRunner(timeout_s=90))
            results = [run_incident(db, loop, s, workdir, arm, operator) for s in specs]
        table = OwnershipTable.from_ledger(db)
        return {
            "arm": arm, "incidents": results, "summary": summarise(results),
            "final_standings": [s.as_dict() for s in table.all()],
            "memory_entries": len(MemoryStore(db).active()),
        }
    finally:
        db.close()
        engine.dispose()


def orderings(specs: list[dict], n: int) -> list[list[dict]]:
    """Ordering 0 is the corpus order; the rest are seeded shuffles. Order matters: BRE learns as it goes."""
    out = [list(specs)]
    for seed in range(1, n):
        shuffled = list(specs)
        random.Random(seed).shuffle(shuffled)
        out.append(shuffled)
    return out


def _stats(values: list[float]) -> dict:
    return {"mean": round(statistics.fmean(values), 4),
            "std": round(statistics.pstdev(values), 4) if len(values) > 1 else 0.0,
            "min": round(min(values), 4), "max": round(max(values), 4), "n": len(values)}


AGG_KEYS = ("resolution_rate", "tokens_per_incident", "wasted_attempts", "memory_diagnoses",
            "memory_refuted", "bob_diagnoses", "mean_attempts")


def compare(specs: list[dict], *, n_orderings: int = 3, arms: tuple[str, ...] = ARMS,
            executor_factory: Callable = ReplayExecutor, progress: Optional[Callable[[str], None]] = None) -> dict:
    runs = []
    for i, order in enumerate(orderings(specs, n_orderings)):
        entry = {"ordering": i, "order": [s["id"] for s in order], "arms": {}}
        for arm in arms:
            if progress:
                progress(f"ordering {i + 1}/{n_orderings}  arm {arm}")
            entry["arms"][arm] = run_arm(order, arm, executor_factory=executor_factory)
        runs.append(entry)

    aggregate = {arm: {k: _stats([r["arms"][arm]["summary"][k] for r in runs]) for k in AGG_KEYS} for arm in arms}
    paired = {}
    if "baseline" in arms:
        for arm in arms:
            if arm == "baseline":
                continue
            paired[f"{arm}_minus_baseline"] = {
                k: _stats([r["arms"][arm]["summary"][k] - r["arms"]["baseline"]["summary"][k] for r in runs])
                for k in ("resolution_rate", "tokens_per_incident", "wasted_attempts")}
    return {"aggregate": aggregate, "paired_differences": paired, "runs": runs}


def verdict(result: dict) -> list[str]:
    """Plain-language findings, generated from the numbers -- including when they are unflattering."""
    agg, paired = result["aggregate"], result["paired_differences"]
    lines: list[str] = []
    if "bre" not in agg or "baseline" not in agg:
        return lines
    d = paired["bre_minus_baseline"]
    n = agg["bre"]["resolution_rate"]["n"]
    tok = d["tokens_per_incident"]
    lines.append(f"Over {n} ordering(s) of the corpus:")
    rr = d["resolution_rate"]["mean"]
    lines.append("- Resolution rate: " + (
        "identical between BRE and Bob alone" if abs(rr) < 1e-9 else
        f"BRE {'higher' if rr > 0 else 'LOWER'} by {abs(rr) * 100:.1f} points (mean paired difference)"))
    if tok["mean"] < -1e-9:
        pct = -tok["mean"] / max(agg["baseline"]["tokens_per_incident"]["mean"], 1e-9) * 100
        lines.append(f"- Nominal token cost per incident: BRE {pct:.1f}% lower "
                     f"({tok['mean']:.0f} +/- {tok['std']:.0f} tokens/incident vs Bob alone). NOMINAL cost model, see note.")
    elif tok["mean"] > 1e-9:
        lines.append(f"- Nominal token cost per incident: BRE was HIGHER by {tok['mean']:.0f} tokens/incident on average. "
                     "Wrongly reused memories cost failed attempts that outweighed the savings. Reported as found.")
    else:
        lines.append("- Nominal token cost per incident: no difference. Reported as found.")
    w = d["wasted_attempts"]
    lines.append(f"- Wasted (failed) attempts: BRE {agg['bre']['wasted_attempts']['mean']:.1f} vs Bob alone "
                 f"{agg['baseline']['wasted_attempts']['mean']:.1f} per run (paired difference {w['mean']:+.1f}).")
    lines.append(f"- BRE served {agg['bre']['memory_diagnoses']['mean']:.1f} diagnoses from verified memory per run and "
                 f"had {agg['bre']['memory_refuted']['mean']:.1f} refuted by the test suite.")
    if "bre_frozen" in agg:
        e, f = agg["bre"]["memory_refuted"]["mean"], agg["bre_frozen"]["memory_refuted"]["mean"]
        lines.append(
            f"- Ablation (ownership frozen at its prior): {f:.1f} refuted reuses per run vs {e:.1f} with ownership evolving. " + (
                "Evolving ownership stopped reusing a memory that kept failing; the frozen arm kept trying it."
                if f > e else "No difference: on this corpus ownership evolution did not change behaviour. Reported as found."))
    lines.append(f"- {COST_NOTE}")
    return lines


def render_markdown(artifact: dict) -> str:
    res, agg = artifact["result"], artifact["result"]["aggregate"]
    out = [f"# BRE vs Bob alone — slice `{artifact.get('slice', 'full')}`", "",
           f"_Generated {artifact['generated_at']} · corpus `{artifact['corpus_sha256'][:12]}` · "
           f"{artifact['corpus_size']} incidents ({artifact.get('look_alikes_in_corpus', 0)} look-alikes) · "
           f"{artifact['orderings']} ordering(s) · tau {artifact['tau']} "
           f"({artifact['tau_source']}) · Bob: **{artifact['bob_mode']}**_", "", "## Findings", ""]
    out += verdict(res)
    out += ["", "## Per arm (mean ± std across orderings)", "",
            "| arm | resolution | tokens/incident (nominal) | Bob diagnoses | memory diagnoses | refuted reuses | wasted attempts |",
            "|---|---|---|---|---|---|---|"]
    for arm, a in agg.items():
        out.append(f"| {arm} | {a['resolution_rate']['mean'] * 100:.1f}% ± {a['resolution_rate']['std'] * 100:.1f} | "
                   f"{a['tokens_per_incident']['mean']:.0f} ± {a['tokens_per_incident']['std']:.0f} | "
                   f"{a['bob_diagnoses']['mean']:.1f} | {a['memory_diagnoses']['mean']:.1f} | "
                   f"{a['memory_refuted']['mean']:.1f} | {a['wasted_attempts']['mean']:.1f} |")
    out += ["", "## Limits", "", f"- {COST_NOTE}",
            "- The corpus is small and synthetic (3 fixture repositories). Look-alike incidents are included on purpose.",
            "- Approvals are automated by the harness; a real run needs a human operator at the gate.",
            "- Verification is a real pytest run in a real git checkout; the diagnosing/fixing agent is a labelled stand-in "
            "unless `--bob live` was used.", ""]
    return "\n".join(out)


def stable_view(artifact: dict) -> dict:
    def scrub(o):
        if isinstance(o, dict):
            return {k: scrub(v) for k, v in o.items() if k not in VOLATILE}
        if isinstance(o, list):
            return [scrub(v) for v in o]
        return o
    return scrub(artifact)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m reliability.evaluation.compare")
    ap.add_argument("--corpus", default="tests/e2e/corpus")
    ap.add_argument("--orderings", type=int, default=3)
    ap.add_argument("--out", default="docs/artifacts")
    ap.add_argument("--tau", type=float, default=None, help="override tau (otherwise: tuned artifact, else ASMOS default)")
    ap.add_argument("--tau-artifact", default=None, help="load tau from a specific tuning artifact (a slice's own tuning)")
    ap.add_argument("--exclude-repo", action="append", default=[], help="drop a fixture repository from the corpus (slices)")
    ap.add_argument("--slice", default="full", help="label for this corpus slice")
    ap.add_argument("--bob", choices=("replay", "live"), default="replay")
    ap.add_argument("--limit", type=int, default=None, help="use only the first N corpus incidents (smoke runs)")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args(argv)

    specs = [s for s in load_corpus(args.corpus) if s["repo"] not in args.exclude_repo][: args.limit]
    if args.tau_artifact:
        data = json.loads(Path(args.tau_artifact).read_text(encoding="utf-8"))
        tau, tau_source = float(data["tau"]), f"tuned:{data.get('artifact', Path(args.tau_artifact).name)}"
    elif args.tau is not None:
        tau, tau_source = args.tau, "cli"
    else:
        tau, tau_source = resolve_tau()
    with _env(BRE_BOB_TRANSPORT="replay" if args.bob == "replay" else None, BRE_TAU=tau,
              BRE_MAX_ATTEMPTS=os.environ.get("BRE_MAX_ATTEMPTS")):
        result = compare(specs, n_orderings=args.orderings,
                         executor_factory=ReplayExecutor if args.bob == "replay" else select_executor,
                         progress=lambda m: print(m, file=sys.stderr))

    artifact = {
        "harness_version": HARNESS_VERSION, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "corpus": str(args.corpus), "corpus_sha256": corpus_digest(args.corpus), "corpus_size": len(specs),
        "orderings": args.orderings, "tau": tau, "tau_source": tau_source, "bob_mode": args.bob,
        "slice": args.slice, "excluded_repos": args.exclude_repo,
        "look_alikes_in_corpus": sum(1 for s in specs if s["repo"] == "connection_cap"),
        "max_attempts": int(os.environ.get("BRE_MAX_ATTEMPTS", 3)), "approvals": "automated by the harness",
        "cost_note": COST_NOTE, "result": result, "findings": verdict(result),
    }
    print("\n".join(artifact["findings"]))
    if not args.no_write:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = out / f"comparison_{args.slice}_{stamp}.json"
        path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        (out / f"comparison_{args.slice}_{stamp}.md").write_text(render_markdown(artifact), encoding="utf-8", newline="\n")
        print(f"artifact: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
