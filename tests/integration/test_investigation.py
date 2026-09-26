"""Stage S2 exit criteria, verified end to end through the API.

    pytest tests/integration/test_investigation.py  -> passes and produces an
    evidence set of >= 5 items across >= 3 source types for the seeded failure
    POST /api/incidents/{id}/investigate -> returns a populated evidence set

The seeded failure: a CI test failure in a connection pool, evidenced by source
files, git history, the failing test itself, a parsed CI log and config.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.database import Base, get_db
from apps.api.main import app


@pytest.fixture
def client(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def _override():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _incident(client, **overrides):
    payload = {
        "repository": "dataforge",
        "branch": "main",
        "type": "test_failure",
        "severity": "high",
        "description": (
            "DatabaseConnector test failed: connection pool exhaustion "
            "in tests/test_dbpool.py"
        ),
        "metadata": {
            "error": "AssertionError: connection pool exhausted after 2 acquisitions",
            "ci_log": "ci/failure.log",
        },
    }
    payload.update(overrides)
    r = client.post("/api/incidents", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _investigate(client, incident_id, *, run_tests=True, repo_path=None):
    body = {"run_tests": run_tests}
    if repo_path is not None:
        body["repo_path"] = str(repo_path)
    return client.post(f"/api/incidents/{incident_id}/investigate", json=body)


# ── the exit criterion ────────────────────────────────────────────────────────

def test_investigate_seeded_failure_produces_evidence_package(client, seeded_repo):
    inc = _incident(client)

    r = _investigate(client, inc["id"], repo_path=seeded_repo)
    assert r.status_code == 200, r.text
    payload = r.json()

    evidence = payload["evidence"]
    source_types = {e["source_type"] for e in evidence}

    # >= 5 items across >= 3 source types (STAGES.md S2 exit criterion)
    assert len(evidence) >= 5, f"only {len(evidence)} evidence items: {evidence}"
    assert len(source_types) >= 3, f"only source types {source_types}"

    # every item carries the contract fields (investigator/__init__.py)
    for item in evidence:
        assert item["source_type"] in {"repository", "git", "test", "ci", "config", "memory"}
        assert item["source_reference"]
        assert 0.0 <= item["relevance_score"] <= 1.0
        assert 0.0 <= item["confidence"] <= 1.0

    # concrete expectations for this failure
    refs = [e["source_reference"] for e in evidence]
    assert "config/app.yaml" in refs, refs
    assert any(ref.startswith("commit:") for ref in refs), refs
    assert any("test_pool_sized_from_config" in ref for ref in refs), refs
    assert any(ref.startswith("run:") for ref in refs), refs

    ci_items = [e for e in evidence if e["source_type"] == "ci"]
    assert ci_items, "CI log evidence missing"
    assert "connection pool exhausted" in ci_items[0]["content"]

    run_items = [e for e in evidence if e["source_reference"].startswith("run:")]
    assert run_items and "FAILED" in run_items[0]["content"]


def test_investigate_transitions_incident_and_completes_investigation(client, seeded_repo):
    inc = _incident(client)
    assert inc["status"] == "DETECTED"

    r = _investigate(client, inc["id"], repo_path=seeded_repo, run_tests=False)
    assert r.status_code == 200, r.text
    investigation = r.json()["investigation"]

    assert investigation["status"] == "completed"
    assert investigation["started_at"] is not None
    assert investigation["completed_at"] is not None
    assert investigation["summary"]
    assert "evidence" in investigation["summary"]

    after = client.get(f"/api/incidents/{inc['id']}").json()
    assert after["status"] == "INVESTIGATING"


def test_evidence_is_persisted_and_fetchable(client, seeded_repo):
    inc = _incident(client)
    r = _investigate(client, inc["id"], repo_path=seeded_repo, run_tests=False)
    inv_id = r.json()["investigation"]["id"]

    rows = client.get(f"/api/investigations/{inv_id}/evidence").json()
    assert len(rows) == len(r.json()["evidence"])
    assert all(row["investigation_id"] == inv_id for row in rows)


def test_second_investigation_appends_new_evidence(client, seeded_repo):
    """Re-investigation is legal from INVESTIGATING and creates a new record."""
    inc = _incident(client)
    first = _investigate(client, inc["id"], repo_path=seeded_repo, run_tests=False)
    second = _investigate(client, inc["id"], repo_path=seeded_repo, run_tests=False)
    assert first.json()["investigation"]["id"] != second.json()["investigation"]["id"]
    assert len(second.json()["evidence"]) >= 5


# ── error paths ───────────────────────────────────────────────────────────────

def test_investigate_unknown_incident_is_404(client, seeded_repo):
    r = _investigate(client, "does-not-exist", repo_path=seeded_repo)
    assert r.status_code == 404


def test_investigate_refuses_non_startable_state(client, seeded_repo):
    inc = _incident(client)
    for status in ["INVESTIGATING", "DIAGNOSED"]:
        client.post(f"/api/incidents/{inc['id']}/transition", params={"new_status": status})
    r = _investigate(client, inc["id"], repo_path=seeded_repo)
    assert r.status_code == 409
    assert "DIAGNOSED" in r.json()["detail"]


def test_investigate_without_resolvable_repo_is_409(client, monkeypatch):
    """No repo_path anywhere -> the API must say so, not guess a path."""
    monkeypatch.delenv("BRE_REPO_ROOT", raising=False)
    inc = _incident(client)
    r = _investigate(client, inc["id"], repo_path=None)
    assert r.status_code == 409
    assert "repo_path" in r.json()["detail"]


def test_investigate_missing_directory_is_409(client):
    inc = _incident(client)
    r = _investigate(client, inc["id"], repo_path="/definitely/not/a/repo")
    assert r.status_code == 409
