"""Shared fixtures for the test suite.

`seeded_repo` builds the S2 target repository at runtime via the same builder
the evaluation harness uses -- one story, one implementation (see
reliability/evaluation/fixtures.py for why history is constructed here).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from reliability.evaluation.fixtures import build_fixture_repo


@pytest.fixture
def seeded_repo(tmp_path: Path) -> Path:
    """A copy of the seeded-failure fixture with real git history."""
    return build_fixture_repo("seeded_failure", tmp_path / "seeded_failure")


@pytest.fixture
def auth_repo(tmp_path: Path) -> Path:
    """A copy of the auth-timeout fixture with real git history."""
    return build_fixture_repo("auth_timeout", tmp_path / "auth_timeout")
