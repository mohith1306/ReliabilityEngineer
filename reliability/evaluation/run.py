"""Evaluation harness -- run the corpus, grade the pipeline, stamp an artifact.

    python -m reliability.evaluation.run --corpus tests/e2e/corpus [--out runs]

Per incident:
    1. build the seeded fixture repo (fresh git history)
    2. create the incident and run the real investigation service
    3. open an OutcomeRecord for the investigator's evidence claim (prediction
       time -- the outcome is not yet known) carrying cost and components
    4. grade the evidence against the corpus expectation
    5. close the record: confirmed / refuted, against an `eval:` run id

The artifact records per-incident outcome, token count and wall time
(ARCHITECTURE.md section 30 / ADR-0003). Tokens are 0 while the pipeline makes
no LLM calls; the field exists from the first write because it cannot be
backfilled (ERRATA A8).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.database import Base, IncidentDB
from apps.api.services.investigation_service import run_investigation
from models.outcome import ClaimClass, OutcomeRecordCreate, OutcomeStatus, PredictionType
from reliability.evaluation.fixtures import build_fixture_repo
from reliability.ledger.record import OutcomeLedger

HARNESS_VERSION = 1
EVALUATOR_ID = "evaluation-harness"
EVAL_RUN_PREFIX = "eval:"

# Fields that legitimately differ between two runs of the same corpus.
VOLATILE_FIELDS = frozenset({"generated_at", "cost_wall_ms", "total_wall_ms"})


# ── corpus loading ────────────────────────────────────────────────────────────

def load_corpus(corpus_dir: str | Path) -> list[dict]:
    """Load and validate every incident spec, sorted by id for determinism."""
    corpus_dir = Path(corpus_dir)
    if not corpus_dir.is_dir():
        raise FileNotFoundError(f"corpus directory not found: {corpus_dir}")

    specs: list[dict] = []
    for path in sorted(corpus_dir.glob("*.json")):
        spec = json.loads(path.read_text())
        for key in ("id", "repo", "topic", "incident", "expected"):
            if key not in spec:
                raise ValueError(f"{path.name}: missing required key {key!r}")
        must = spec["expected"].get("must_surface")
        if not isinstance(must, list) or not must:
            raise ValueError(f"{path.name}: expected.must_surface must be a list")
        if "description" not in spec["incident"]:
            raise ValueError(f"{path.name}: incident.description is required")
        specs.append(spec)

    specs.sort(key=lambda s: s["id"])
    ids = [s["id"] for s in specs]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate incident ids in corpus: {ids}")
    return specs


def corpus_digest(corpus_dir: str | Path) -> str:
    """sha256 over (filename, bytes) pairs -- pins what was actually graded."""
    digest = hashlib.sha256()
    for path in sorted(Path(corpus_dir).glob("*.json")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


# ── grading ───────────────────────────────────────────────────────────────────

def grade(evidence: list[tuple[str, str]], expected: dict) -> dict:
    """Evidence is [(source_type, source_reference), ...]. All expectations must
    appear as substrings of some reference, plus the count thresholds."""
    refs = [ref for _, ref in evidence]
    sources = {st for st, _ in evidence}

    checks: list[dict] = []
    for want in expected["must_surface"]:
        checks.append({
            "expect": want,
            "found": any(want in ref for ref in refs),
        })

    min_evidence = expected.get("min_evidence", 1)
    checks.append({"expect": f"evidence_count >= {min_evidence}",
                   "found": len(evidence) >= min_evidence})
    min_types = expected.get("min_source_types", 1)
    checks.append({"expect": f"source_types >= {min_types}",
                   "found": len(sources) >= min_types})

    missing = [c["expect"] for c in checks if not c["found"]]
    return {
        "checks": {"total": len(checks), "passed": len(checks) - len(missing)},
        "missing": missing,
    }


# ── one incident ──────────────────────────────────────────────────────────────

def run_incident(db, spec: dict, workdir: Path, *, eval_run_id: str) -> dict:
    seed_id = spec["id"]
    repo = build_fixture_repo(spec["repo"], workdir / seed_id)

    incident_row = IncidentDB(
        id=f"inc_{seed_id}",
        repository=spec["repo"],
        branch=spec["incident"].get("branch", "main"),
        type=spec["incident"].get("type", "test_failure"),
        severity=spec["incident"].get("severity", "medium"),
        status="DETECTED",
        description=spec["incident"]["description"],
        metadata_json=spec["incident"].get("metadata", {}),
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(incident_row)
    db.flush()

    ledger = OutcomeLedger(db)
    started = time.perf_counter()
    investigation, evidence_rows, incident_row = run_investigation(
        db, incident_row, repo_path=str(repo), run_tests=False,
    )
    wall_ms = (time.perf_counter() - started) * 1000.0

    evidence = [(e.source_type, e.source_reference) for e in evidence_rows]
    ordered = sorted(evidence_rows, key=lambda e: -e.relevance_score)
    top_refs = [e.source_reference for e in ordered[:5]]
    top3 = [e.relevance_score for e in ordered[:3]] or [0.0]
    confidence = round(sum(top3) / len(top3), 4)
    source_types = sorted({e.source_type for e in evidence_rows})

    # Prediction time: the investigator's claim, before the grade is known.
    record = ledger.open(
        OutcomeRecordCreate(
            incident_id=incident_row.id,
            predictor_id=EVALUATOR_ID,
            topic=spec["topic"],
            prediction_type=PredictionType.DIAGNOSIS,
            prediction_payload={"top_evidence": top_refs, "seed": seed_id},
            claim_class=ClaimClass.B,
            confidence=confidence,
            components={
                "evidence_count": len(evidence_rows),
                "source_types": len(source_types),
                "mean_relevance_top3": confidence,
            },
        ),
        cost_tokens=0,  # no LLM calls in the S3 pipeline; recorded from write 1
        cost_wall_ms=wall_ms,
        record_id=f"out_{seed_id}",
    )

    result = grade(evidence, spec["expected"])
    passed = not result["missing"]
    closed = ledger.close(
        record.id,
        OutcomeStatus.CONFIRMED if passed else OutcomeStatus.REFUTED,
        closed_by=EVALUATOR_ID,
        verification_run_id=f"{EVAL_RUN_PREFIX}{eval_run_id}",
    )

    return {
        "id": seed_id,
        "incident_id": incident_row.id,
        "repo": spec["repo"],
        "topic": spec["topic"],
        "outcome": closed.status.value,
        "prediction_confidence": confidence,
        "checks": result["checks"],
        "missing": result["missing"],
        "evidence_count": len(evidence_rows),
        "source_types": source_types,
        "cost_tokens": record.cost_tokens,
        "cost_wall_ms": round(record.cost_wall_ms, 3),
        "record_id": record.id,
    }


# ── whole corpus ──────────────────────────────────────────────────────────────

def run_corpus(corpus_dir: str | Path, *, out_dir: str | Path | None = None) -> dict:
    """Run every corpus incident against an isolated in-memory database."""
    specs = load_corpus(corpus_dir)
    eval_run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()

    results: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="bre-eval-") as tmp:
        workdir = Path(tmp)
        for spec in specs:
            results.append(run_incident(db, spec, workdir, eval_run_id=eval_run_id))
            db.commit()

    confirmed = sum(1 for r in results if r["outcome"] == "confirmed")
    refuted = sum(1 for r in results if r["outcome"] == "refuted")
    total_wall = sum(r["cost_wall_ms"] for r in results)
    total_tokens = sum(r["cost_tokens"] for r in results)

    artifact = {
        "harness_version": HARNESS_VERSION,
        "corpus": str(corpus_dir),
        "corpus_sha256": corpus_digest(corpus_dir),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "incidents": results,
        "summary": {
            "total": len(results),
            "confirmed": confirmed,
            "refuted": refuted,
            "total_tokens": total_tokens,
            "total_wall_ms": round(total_wall, 3),
        },
    }

    if out_dir is not None:
        out_path = Path(out_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        artifact_path = out_path / f"evaluation_{stamp}.json"
        artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
        artifact["artifact_path"] = str(artifact_path)

    db.close()
    engine.dispose()
    return artifact


def stable_view(artifact: dict) -> dict:
    """The artifact minus its volatile fields -- what determinism means here.

    Two runs over an unchanged corpus must agree on every outcome, count,
    confidence and digest. Wall times and the generation stamp may differ; that
    is measurement, not behaviour.
    """
    def scrub(obj):
        if isinstance(obj, dict):
            return {k: scrub(v) for k, v in obj.items() if k not in VOLATILE_FIELDS}
        if isinstance(obj, list):
            return [scrub(v) for v in obj]
        return obj

    return scrub({k: v for k, v in artifact.items() if k != "artifact_path"})


# ── CLI ───────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m reliability.evaluation.run",
        description="Run the seeded-failure corpus and stamp a JSON artifact.",
    )
    parser.add_argument("--corpus", default="tests/e2e/corpus")
    parser.add_argument("--out", default="runs")
    args = parser.parse_args(argv)

    artifact = run_corpus(args.corpus, out_dir=args.out)
    summary = artifact["summary"]
    print(
        f"{summary['total']} incidents: {summary['confirmed']} confirmed, "
        f"{summary['refuted']} refuted | {summary['total_tokens']} tokens | "
        f"{summary['total_wall_ms']:.0f}ms | {artifact.get('artifact_path', 'no out dir')}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
