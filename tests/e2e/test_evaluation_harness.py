"""Evaluation harness end to end. S3 exit criteria 3-5:

    - a seeded-failure corpus of >= 10 reproducible incidents under tests/e2e/corpus/
    - `python -m reliability.evaluation.run --corpus tests/e2e/corpus` emits a
      stamped JSON artifact with per-incident outcome, token count and wall time
    - re-running the harness on an unchanged corpus reproduces the artifact
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from reliability.evaluation.run import load_corpus, run_corpus, stable_view

CORPUS = Path(__file__).parent / "corpus"
REPO_ROOT = Path(__file__).resolve().parents[2]


def test_corpus_has_at_least_ten_reproducible_incidents():
    specs = load_corpus(CORPUS)
    assert len(specs) >= 10, f"corpus has only {len(specs)} incidents"
    ids = [s["id"] for s in specs]
    assert len(ids) == len(set(ids))
    repos = {s["repo"] for s in specs}
    assert len(repos) >= 2, "corpus should span more than one fixture repository"


def test_harness_runs_the_whole_corpus(tmp_path):
    artifact = run_corpus(CORPUS, out_dir=tmp_path)

    assert artifact["summary"]["total"] >= 10
    assert artifact["generated_at"]
    assert artifact["corpus_sha256"]
    assert artifact["summary"]["total_tokens"] >= 0  # 0 until Bob lands (S4)
    assert artifact["summary"]["total_wall_ms"] > 0

    for row in artifact["incidents"]:
        assert row["outcome"] in {"confirmed", "refuted"}
        assert row["checks"]["total"] >= row["checks"]["passed"] >= 1
        assert isinstance(row["cost_tokens"], int)
        assert row["cost_wall_ms"] > 0
        assert row["evidence_count"] >= 5
        assert row["record_id"].startswith("out_")


def test_every_seed_incident_confirms(tmp_path):
    """The corpus exists to be found. A refutation means either the pipeline
    regressed or the expectation is wrong -- both must surface, not hide."""
    artifact = run_corpus(CORPUS, out_dir=tmp_path)
    refuted = [r for r in artifact["incidents"] if r["outcome"] == "refuted"]
    assert not refuted, f"refuted seeds: {[(r['id'], r['missing']) for r in refuted]}"


def test_cli_emits_a_stamped_artifact(tmp_path):
    """The literal exit-criteria command."""
    proc = subprocess.run(
        [sys.executable, "-m", "reliability.evaluation.run",
         "--corpus", str(CORPUS), "--out", str(tmp_path)],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    assert "confirmed" in proc.stdout

    artifacts = sorted(tmp_path.glob("evaluation_*.json"))
    assert len(artifacts) == 1, f"expected exactly one artifact, got {artifacts}"

    data = json.loads(artifacts[0].read_text())
    assert data["harness_version"] == 1
    assert data["summary"]["total"] >= 10
    assert data["incidents"][0]["outcome"] in {"confirmed", "refuted"}


def test_rerun_reproduces_the_artifact(tmp_path):
    """Determinism: identical corpus -> identical outcomes, counts, digests.

    Wall times and the generation stamp are measurement, not behaviour, and are
    excluded by stable_view (run.py VOLATILE_FIELDS).
    """
    first = run_corpus(CORPUS, out_dir=tmp_path / "a")
    second = run_corpus(CORPUS, out_dir=tmp_path / "b")

    assert stable_view(first) == stable_view(second)

    file_a = json.loads(sorted((tmp_path / "a").glob("evaluation_*.json"))[0].read_text())
    file_b = json.loads(sorted((tmp_path / "b").glob("evaluation_*.json"))[0].read_text())
    assert stable_view(file_a) == stable_view(file_b)
    assert first["corpus_sha256"] == second["corpus_sha256"]


def test_missing_expectation_refutes_not_crashes(tmp_path):
    """Grading honesty: an expectation nothing can satisfy is reported refuted."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "broken.json").write_text(json.dumps({
        "id": "broken-001",
        "repo": "seeded_failure",
        "topic": "database",
        "incident": {"type": "test_failure", "description": "connection pool exhausted"},
        "expected": {"must_surface": ["this_file_does_not_exist.py"], "min_evidence": 1},
    }))
    artifact = run_corpus(corpus, out_dir=tmp_path / "out")
    row = artifact["incidents"][0]
    assert row["outcome"] == "refuted"
    assert row["missing"] == ["this_file_does_not_exist.py"]
