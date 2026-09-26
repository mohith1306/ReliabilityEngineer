"""Shared fixtures for the test suite.

`seeded_repo` builds the S2 target repository at runtime via the same builder
the evaluation harness uses -- one story, one implementation (see
reliability/evaluation/fixtures.py for why history is constructed here).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.database import Base
from reliability.evaluation.fixtures import build_fixture_repo


@pytest.fixture
def db():
    """A throwaway in-memory database with the full schema. One per test."""
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def seeded_repo(tmp_path: Path) -> Path:
    """A copy of the seeded-failure fixture with real git history."""
    return build_fixture_repo("seeded_failure", tmp_path / "seeded_failure")


@pytest.fixture
def auth_repo(tmp_path: Path) -> Path:
    """A copy of the auth-timeout fixture with real git history."""
    return build_fixture_repo("auth_timeout", tmp_path / "auth_timeout")
