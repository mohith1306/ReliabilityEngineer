#!/usr/bin/env python
"""Walk one incident through the whole BRE loop in the terminal.

    python scripts/demo.py                          # config-regression incident, simulated Bob, asks you to approve
    python scripts/demo.py --twice                  # the same failure again: watch it answered from verified memory
    python scripts/demo.py --scenario connection_cap --twice   # a look-alike: watch the tests refute a wrong reuse
    python scripts/demo.py --live                   # real IBM Bob (needs Bob Shell + BOB_API_KEY)
    python scripts/demo.py --yes                    # approve automatically (for recordings / CI)

Everything except the agent is real: a throwaway git repository, a real checkpoint and branch, real pytest
runs at three verification levels, a real rollback on failure, and the real outcome ledger. Unless --live is
given, the diagnosing/fixing agent is the labelled replay stand-in, and every screen says so.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
import tempfile
import textwrap
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

C = {"dim": "2", "b": "1", "g": "32", "r": "31", "y": "33", "c": "36", "m": "35"}
USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def paint(text: str, *styles: str) -> str:
    if not USE_COLOR:
        return text
    return "".join(f"\033[{C[s]}m" for s in styles) + text + "\033[0m"


def say(text: str = "", *styles: str) -> None:
    print(paint(text, *styles))


def rule(title: str) -> None:
    say(f"\n── {title} " + "─" * max(4, 74 - len(title)), "c", "b")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # the symbols must never crash a cp1252 console
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", default="seeded_failure", choices=["seeded_failure", "auth_timeout", "connection_cap"])
    ap.add_argument("--twice", action="store_true", help="run the same scenario twice to show memory reuse")
    ap.add_argument("--live", action="store_true", help="use real IBM Bob (Bob Shell + BOB_API_KEY)")
    ap.add_argument("--yes", action="store_true", help="approve automatically instead of asking")
    ap.add_argument("--tau", type=float, default=0.30, help="routing threshold (default 0.30 for the demo)")
    args = ap.parse_args()

    if not args.live:
        os.environ["BRE_BOB_TRANSPORT"] = "replay"
    else:
        os.environ.pop("BRE_BOB_TRANSPORT", None)
    os.environ["BRE_TAU"] = str(args.tau)

    from apps.api.database import ApprovalDB, IncidentDB, OperatorDB, OutcomeRecordDB, RiskAssessmentDB, generate_id
    from asmos_bridge.ownership.ledger import OwnershipTable
    from reliability.evaluation.compare import _new_session
    from reliability.evaluation.fixtures import build_fixture_repo
    from reliability.evaluation.run import load_corpus
    from reliability.orchestration.lifecycle import Lifecycle
    from reliability.orchestration.loop import ReliabilityLoop
    from reliability.orchestration.routed import routed_diagnoser
    from reliability.remediation import git_ops
    from reliability.remediation.allowlist import RepoAllowlist
    from reliability.remediation.executors import select_executor

    seed = {"seeded_failure": "seed-001", "auth_timeout": "seed-007", "connection_cap": "seed-011"}[args.scenario]
    spec = next(s for s in load_corpus(ROOT / "tests" / "e2e" / "corpus") if s["id"] == seed)

    say("BOB RELIABILITY ENGINEER — one incident, end to end", "b")
    say("Bob: " + ("LIVE IBM BOB" if args.live else "SIMULATED (labelled replay stand-in). Verification below is REAL."),
        "g" if args.live else "y", "b")

    engine, db = _new_session()
    operator = OperatorDB(id=generate_id(), name=f"{getpass.getuser()} (local CLI operator)", api_key_hash="cli")
    db.add(operator)
    db.commit()

    with tempfile.TemporaryDirectory(prefix="bre-demo-") as tmp:
        work = Path(tmp)
        loop = ReliabilityLoop(db, diagnoser=routed_diagnoser, executor_factory=select_executor,
                               allowlist=RepoAllowlist([work]))

        for n in range(2 if args.twice else 1):
            title = f"INCIDENT {n + 1}" if args.twice else "INCIDENT"
            rule(title)
            repo = build_fixture_repo(spec["repo"], work / f"repo{n}")
            meta = dict(spec["incident"].get("metadata", {}))
            meta.update({"repo_path": str(repo), "topic": spec["topic"]})
            row = IncidentDB(id=f"demo{n + 1}", repository=spec["repo"], type=spec["incident"]["type"], severity="high",
                             status="DETECTED", description=spec["incident"]["description"], metadata_json=meta)
            db.add(row)
            db.commit()
            say(textwrap.fill(row.description, 78))
            base = (git_ops.current_branch(repo), git_ops.head_sha(repo))

            for _ in range(20):
                res = loop.advance(row.id)
                db.refresh(row)
                for s in res.steps:
                    color = "g" if s.action in ("verify",) and s.data.get("passed") else "r" if s.action in ("verify", "remediation_failed") and not s.data.get("passed", False) else "c"
                    say(f"  {s.action:<18} → {s.to_status:<16} {s.note[:96]}", color)
                if res.blocked_on == "approval":
                    risk = db.query(RiskAssessmentDB).filter_by(incident_id=row.id).order_by(RiskAssessmentDB.created_at.desc()).first()
                    say(f"\n  ✋ {risk.risk_level} risk (score {risk.factors['score']}). Nothing has been written to the repository.", "y", "b")
                    for k, v in risk.factors["rules"].items():
                        if v["points"]:
                            say(f"       {k:<22} input={v['input']!s:<10} +{v['points']}", "dim")
                    ok = args.yes or input("  Approve this remediation? [y/N] ").strip().lower().startswith("y")
                    db.add(ApprovalDB(id=generate_id(), incident_id=row.id, risk_level=risk.risk_level,
                                      decision="APPROVED" if ok else "REJECTED", operator_id=operator.id,
                                      operator_name=operator.name, reason="demo CLI", created_at=datetime.now(timezone.utc).replace(tzinfo=None)))
                    db.commit()
                    say(f"  {'✔ approved' if ok else '✘ rejected'} by {operator.name}", "g" if ok else "r")
                    continue
                break

            say(f"\n  final state: {row.status}   attempts: {row.attempt}", "g" if row.status == "RESOLVED" else "r", "b")
            after = (git_ops.current_branch(repo), git_ops.head_sha(repo))
            say(f"  your checkout: {after[0]} @ {after[1][:8]} — {'untouched' if after == base else 'CHANGED'}"
                f"; the fix lives on its own bre/* branch for review", "dim")
            for r in db.query(OutcomeRecordDB).filter_by(incident_id=row.id).order_by(OutcomeRecordDB.predicted_at):
                if r.prediction_type in ("diagnosis", "routing"):
                    extra = (r.components.get("reason") or "") if r.prediction_type == "routing" else ""
                    say(f"  ledger: {r.prediction_type:<9} attempt {r.attempt_number} {r.predictor_id:<14} "
                        f"{r.status:<9} {r.cost_tokens:>5} tokens  {extra[:60]}", "dim")

        rule("WHAT BRE HAS LEARNED (computed only from verification-backed ledger closures)")
        for s in OwnershipTable.from_ledger(db).all():
            say(f"  {s.source:<8} {s.topic:<10} verified {s.verified_correct}/{s.verified_total}   trust {s.trust:.3f}   "
                f"share {s.contribution_share:.2f}   ownership {s.ownership:.3f}")
        if not args.live:
            say("\n  Token figures are nominal (simulated agent). Run with --live for measured Bob cost.", "y")
    db.close()
    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
