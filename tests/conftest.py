"""Shared fixtures for the test suite.

`seeded_repo` builds the S2 target repository at runtime: the fixture files are
copied to a tmp dir and given a two-commit git history (import, then the
pool-size regression). The fixture tree itself cannot ship a .git directory --
git refuses to commit a nested repository -- so history is constructed here.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

FIXTURE_SRC = Path(__file__).parent / "fixtures" / "seeded_failure"

GIT_ID = ["-c", "user.email=bre-test@example.com", "-c", "user.name=BRE Test"]


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *GIT_ID, *args],
        cwd=repo, capture_output=True, text=True, check=True,
    )
    return result.stdout


@pytest.fixture
def seeded_repo(tmp_path: Path) -> Path:
    """A copy of the seeded-failure fixture with real git history."""
    repo = tmp_path / "seeded_failure"
    shutil.copytree(FIXTURE_SRC, repo)

    config = repo / "config" / "app.yaml"
    original = config.read_text()
    config.write_text(original.replace("pool_size: 2", "pool_size: 20"))

    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "import dataforge connection pool")

    config.write_text(original)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "lower database pool_size to 2 under memory pressure")

    return repo
