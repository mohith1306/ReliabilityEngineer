"""Stage S2 exit criteria for the four MVP connectors, verified directly.

Each block closes one line of docs/stages/STAGES.md "S2 -- Evidence collection":
  - RepositoryConnector lists source files and detects project type
  - GitConnector returns commit history, blame and diffs for a named file
  - TestConnector discovers tests and returns a structured pass/fail result
  - CIConnector parses a real CI failure log into a structured failure record
"""

from __future__ import annotations

from pathlib import Path

import pytest

from connectors.ci import CIConnector
from connectors.git import GitConnector
from connectors.repository import RepositoryConnector
from connectors.tests import TestConnector

CI_LOG = Path(__file__).parent.parent / "fixtures" / "seeded_failure" / "ci" / "failure.log"


# ── RepositoryConnector ───────────────────────────────────────────────────────

def test_repository_lists_source_files(seeded_repo):
    paths = [f.path for f in RepositoryConnector().list_files(str(seeded_repo))]
    assert "dbpool.py" in paths
    assert "tests/test_dbpool.py" in paths
    assert "config/app.yaml" in paths
    assert not any(p.startswith(".git/") for p in paths)


def test_repository_detects_project_type(seeded_repo):
    assert RepositoryConnector().detect_project_type(str(seeded_repo)) == "python"


def test_repository_refuses_path_traversal(seeded_repo):
    connector = RepositoryConnector()
    with pytest.raises(ValueError, match="escapes"):
        connector.read_file(str(seeded_repo), "../../etc/passwd")


def test_repository_find_files_matching(seeded_repo):
    hits = RepositoryConnector().find_files_matching(str(seeded_repo), ["pool", "dbpool"])
    paths = [p for p, _ in hits]
    assert "dbpool.py" in paths
    assert "tests/test_dbpool.py" in paths


# ── GitConnector ──────────────────────────────────────────────────────────────

def test_git_recent_commits(seeded_repo):
    commits = GitConnector().recent_commits(str(seeded_repo), limit=5)
    assert len(commits) == 2
    assert commits[0].message.startswith("lower database pool_size")
    assert commits[0].short_sha == commits[0].sha[:7]
    assert commits[0].author


def test_git_log_for_paths(seeded_repo):
    commits = GitConnector().log_for_paths(str(seeded_repo), ["dbpool.py"], limit=5)
    assert commits, "expected history for dbpool.py"
    assert any("connection pool" in c.message for c in commits)


def test_git_blame(seeded_repo):
    rows = GitConnector().blame(str(seeded_repo), "dbpool.py")
    assert rows
    assert {"line", "sha", "author"} <= set(rows[0])


def test_git_diff_for_commit_contains_pool_change(seeded_repo):
    commits = GitConnector().recent_commits(str(seeded_repo), limit=5)
    target = next(c for c in commits if "pool_size" in c.message)
    diffs = GitConnector().diff_for_commit(str(seeded_repo), target.sha)
    text = "\n".join(d.diff for d in diffs)
    assert "pool_size" in text
    assert "2" in text and "20" in text


# ── TestConnector ─────────────────────────────────────────────────────────────

def test_test_discovery(seeded_repo):
    discovered = TestConnector().discover(str(seeded_repo))
    labels = {f"{t.file}::{t.name}" for t in discovered}
    assert "tests/test_dbpool.py::test_pool_sized_from_config" in labels
    assert "tests/test_dbpool.py::test_release_returns_slot" in labels


def test_test_run_returns_structured_result(seeded_repo):
    result = TestConnector().run(str(seeded_repo))
    assert result.passed is False
    assert result.returncode != 0
    assert result.command  # recorded for the evidence trail
    failed = [c for c in result.cases if not c.passed]
    assert failed, "expected at least one structured failure"
    assert "test_pool_sized_from_config" in failed[0].name
    assert failed[0].error


# ── CIConnector ───────────────────────────────────────────────────────────────

def test_ci_parses_real_failure_log():
    record = CIConnector().parse_file(str(CI_LOG))
    assert record.failed_count == 1
    assert record.passed_count == 1
    assert len(record.failures) == 1
    failure = record.failures[0]
    assert failure.reference == "tests/test_dbpool.py::test_pool_sized_from_config"
    assert "connection pool exhausted" in (failure.reason or "")


def test_ci_parses_inline_text():
    log = "FAILED tests/a.py::test_x - ValueError: boom\n1 failed in 0.1s"
    record = CIConnector().parse_text(log, source="inline")
    assert record.failed_count == 1
    assert record.failures[0].reference == "tests/a.py::test_x"
    assert record.failures[0].reason == "ValueError: boom"
