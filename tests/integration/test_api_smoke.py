"""End-to-end smoke test for the Phase 1 API surface.

Confirms stage S1 is genuinely DONE rather than assumed, and pins the integrity
gaps recorded in docs/architecture/ERRATA.md so they cannot be quietly forgotten.

Runs against a throwaway SQLite file, never the working ./bre.db.
"""

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
        "description": "DatabaseConnector test failed",
        "metadata": {"job": "ci-4821"},
    }
    payload.update(overrides)
    r = client.post("/api/incidents", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ── service basics ────────────────────────────────────────────────────────────

def test_health(client):
    assert client.get("/health").json() == {"status": "healthy"}


def test_create_and_fetch_incident(client):
    created = _incident(client)
    assert created["status"] == "DETECTED"
    assert created["metadata"] == {"job": "ci-4821"}

    fetched = client.get(f"/api/incidents/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == created["id"]


def test_missing_incident_is_404(client):
    assert client.get("/api/incidents/does-not-exist").status_code == 404


def test_list_filters_by_repository(client):
    _incident(client, repository="dataforge")
    _incident(client, repository="other-repo")
    rows = client.get("/api/incidents", params={"repository": "dataforge"}).json()
    assert [r["repository"] for r in rows] == ["dataforge"]


# ── state machine ─────────────────────────────────────────────────────────────

def test_happy_path_transitions(client):
    inc = _incident(client)
    path = [
        "INVESTIGATING", "DIAGNOSED", "RISK_ASSESSED", "AWAITING_APPROVAL",
        "REMEDIATING", "VERIFYING", "RESOLVED", "CLOSED",
    ]
    for target in path:
        r = client.post(
            f"/api/incidents/{inc['id']}/transition", params={"new_status": target}
        )
        assert r.status_code == 200, f"{target}: {r.text}"
        assert r.json()["status"] == target


def test_illegal_transition_is_rejected(client):
    inc = _incident(client)
    r = client.post(
        f"/api/incidents/{inc['id']}/transition", params={"new_status": "RESOLVED"}
    )
    assert r.status_code == 400
    assert "Invalid transition" in r.json()["detail"]


def test_closed_is_terminal(client):
    """CLOSED has no outgoing edges -- nothing may reopen an incident."""
    inc = _incident(client)
    for target in ["INVESTIGATING", "DIAGNOSED", "RISK_ASSESSED", "AWAITING_APPROVAL"]:
        client.post(f"/api/incidents/{inc['id']}/transition", params={"new_status": target})
    client.post(f"/api/incidents/{inc['id']}/transition", params={"new_status": "CLOSED"})
    r = client.post(
        f"/api/incidents/{inc['id']}/transition", params={"new_status": "INVESTIGATING"}
    )
    assert r.status_code == 400


def test_unknown_status_is_rejected(client):
    inc = _incident(client)
    r = client.post(
        f"/api/incidents/{inc['id']}/transition", params={"new_status": "BANANA"}
    )
    assert r.status_code == 400


# ── investigations + evidence ─────────────────────────────────────────────────

def test_investigation_evidence_roundtrip(client):
    inc = _incident(client)
    inv = client.post("/api/investigations", json={"incident_id": inc["id"]}).json()
    assert inv["status"] == "pending"

    ev = client.post(
        f"/api/investigations/{inv['id']}/evidence",
        json={
            "source_type": "git",
            "source_reference": "commit:8f32a",
            "content": "pool size lowered from 20 to 2",
            "relevance_score": 0.83,
            "confidence": 0.9,
        },
    )
    assert ev.status_code == 201, ev.text

    listed = client.get(f"/api/investigations/{inv['id']}/evidence").json()
    assert len(listed) == 1
    assert listed[0]["source_reference"] == "commit:8f32a"

    done = client.post(
        f"/api/investigations/{inv['id']}/complete", params={"summary": "pool exhaustion"}
    ).json()
    assert done["status"] == "completed"
    assert done["completed_at"] is not None


# ── known gaps, pinned so they cannot be silently forgotten ───────────────────

@pytest.mark.xfail(reason="ERRATA: no FK constraint or existence check on incident_id", strict=True)
def test_investigation_requires_a_real_incident(client):
    r = client.post("/api/investigations", json={"incident_id": "totally-made-up"})
    assert r.status_code in (400, 404)


@pytest.mark.xfail(reason="ERRATA: create_investigation never sets started_at", strict=True)
def test_investigation_records_when_it_started(client):
    inc = _incident(client)
    inv = client.post("/api/investigations", json={"incident_id": inc["id"]}).json()
    assert inv["started_at"] is not None


@pytest.mark.xfail(reason="ERRATA A5: no DETECTED -> CLOSED edge for false alarms", strict=True)
def test_false_alarm_can_be_closed(client):
    inc = _incident(client)
    r = client.post(f"/api/incidents/{inc['id']}/transition", params={"new_status": "CLOSED"})
    assert r.status_code == 200
