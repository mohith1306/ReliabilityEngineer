"""S5 exit criteria: risk classification, verified approval identity, gate.

    - RiskClassifier returns a level PLUS its factor breakdown
    - same inputs -> same level (reproducibility, asserted)
    - approvals carry identity resolved from a bearer API key, never from
      the request body
    - HIGH/CRITICAL cannot reach REMEDIATING without a fresh approval row
    - a direct transition call cannot bypass the gate (403)
"""

from __future__ import annotations

import random

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api import auth
from apps.api.database import Base, OutcomeRecordDB, get_db
from apps.api.main import app
from models.incident import IncidentStatus
from models.risk import RiskLevel
from reliability.orchestration import gate
from reliability.risk.classifier import RiskClassifier
from reliability.risk.policies import ApprovalPolicy, Requirement

OPERATOR_KEY = "s5-test-operator-key"
OPERATOR_NAME = "test-operator"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv(auth.ENV_KEY, OPERATOR_KEY)
    monkeypatch.setenv(auth.ENV_NAME, OPERATOR_NAME)
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


def _incident(client, severity="high", **overrides):
    payload = {
        "repository": "dataforge",
        "branch": "main",
        "type": "test_failure",
        "severity": severity,
        "description": "connection pool exhaustion in tests/test_dbpool.py",
        "metadata": {"error": "AssertionError: connection pool exhausted"},
    }
    payload.update(overrides)
    r = client.post("/api/incidents", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _auth(key=OPERATOR_KEY):
    return {"Authorization": f"Bearer {key}"}


def _walk_to_risk(client, incident_id, *, context=None):
    for status in ("INVESTIGATING", "DIAGNOSED", "RISK_ASSESSED"):
        r = client.post(
            f"/api/incidents/{incident_id}/transition", params={"new_status": status}
        )
        assert r.status_code == 200, r.text
    r = client.post(
        f"/api/incidents/{incident_id}/assess-risk", json=context or {}
    )
    assert r.status_code == 201, r.text
    return r.json()


# ── criterion 1: level + factor breakdown ────────────────────────────────────

def test_classifier_returns_level_and_breakdown():
    assessment = RiskClassifier().classify(
        {"confidence": 0.8},
        {"severity": "high", "database_migration": True, "blast_radius": 4,
         "tests_available": "none", "api_surface_affected": True},
    )
    assert assessment.risk_level in RiskLevel
    factors = assessment.factors
    assert factors["score"] >= 4
    assert factors["rules"]["severity"] == {"input": "high", "points": 2}
    assert factors["rules"]["database_migration"]["points"] == 3
    assert factors["thresholds"]["CRITICAL"] == 7
    assert sum(r["points"] for r in factors["rules"].values()) == factors["score"]


def test_classifier_is_reproducible():
    context = {"severity": "medium", "blast_radius": 3, "tests_available": "partial"}
    first = RiskClassifier().classify({"confidence": 0.7}, context)
    second = RiskClassifier().classify(
        {"confidence": 0.7}, dict(reversed(list(context.items())))
    )
    items = list(context.items())
    random.Random(1).shuffle(items)
    third = RiskClassifier().classify({"confidence": 0.7}, dict(items))

    assert first.risk_level == second.risk_level == third.risk_level
    assert first.factors == second.factors == third.factors
    assert first.blast_radius == third.blast_radius


def test_policy_table():
    policy = ApprovalPolicy()
    assert policy.required_for(RiskLevel.LOW) is Requirement.AUTO
    assert policy.required_for("MEDIUM") is Requirement.HUMAN
    assert policy.required_for(RiskLevel.HIGH) is Requirement.HUMAN
    assert policy.required_for(RiskLevel.CRITICAL) is Requirement.HUMAN
    assert ApprovalPolicy(
        medium_requires_approval=False
    ).required_for("MEDIUM") is Requirement.AUTO


# ── criterion 3: identity comes from the key, not the body ───────────────────

def test_approval_requires_bearer_key(client):
    incident = _incident(client)
    r = client.post(f"/api/incidents/{incident['id']}/approvals",
                    json={"decision": "APPROVED"})
    assert r.status_code == 401

    r = client.post(f"/api/incidents/{incident['id']}/approvals",
                    json={"decision": "APPROVED"}, headers=_auth("wrong-key"))
    assert r.status_code == 401


def test_approval_records_identity_from_key_not_body(client):
    incident = _incident(client)
    _walk_to_risk(client, incident["id"])

    r = client.post(
        f"/api/incidents/{incident['id']}/approvals",
        json={"decision": "APPROVED", "approved_by": "spoofed-admin",
              "operator_id": "spoofed"},
        headers=_auth(),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["operator_name"] == OPERATOR_NAME
    assert body["operator_id"] != "spoofed"
    assert "approved_by" not in body

    rows = client.get(f"/api/incidents/{incident['id']}/approvals").json()
    assert len(rows) == 1
    assert rows[0]["operator_id"] == body["operator_id"]
    assert rows[0]["operator_name"] == OPERATOR_NAME
    assert rows[0]["risk_level"] in {level.value for level in RiskLevel}


def test_auth_creates_operator_from_env_on_first_call(tmp_path, monkeypatch):
    monkeypatch.setenv(auth.ENV_KEY, "bootstrapped-key")
    monkeypatch.setenv(auth.ENV_NAME, "bootstrap-op")
    engine = create_engine(f"sqlite:///{tmp_path / 'b.db'}")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()

    operator = auth.authenticate(db, "Bearer bootstrapped-key")
    assert operator.name == "bootstrap-op"
    with pytest.raises(auth.AuthenticationError):
        auth.authenticate(db, "Bearer some-other-key")


# ── criteria 4 + 5: the gate ─────────────────────────────────────────────────

def test_high_risk_requires_approval_to_remediate(client):
    incident = _incident(client, severity="critical")
    assessment = _walk_to_risk(client, incident["id"])
    assert assessment["risk_level"] in ("HIGH", "CRITICAL")

    r = client.post(
        f"/api/incidents/{incident['id']}/transition",
        params={"new_status": "AWAITING_APPROVAL"},
    )
    assert r.status_code == 200, r.text

    blocked = client.post(
        f"/api/incidents/{incident['id']}/transition",
        params={"new_status": "REMEDIATING"},
    )
    assert blocked.status_code == 403, blocked.text
    assert "verified" in blocked.json()["detail"]

    approved = client.post(
        f"/api/incidents/{incident['id']}/approvals",
        json={"decision": "APPROVED", "reason": "fix is config-only"},
        headers=_auth(),
    )
    assert approved.status_code == 201

    allowed = client.post(
        f"/api/incidents/{incident['id']}/transition",
        params={"new_status": "REMEDIATING"},
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["status"] == "REMEDIATING"


def test_direct_transition_cannot_bypass_the_gate(client):
    """RISK_ASSESSED -> REMEDIATING is a legal edge; the gate still denies it."""
    incident = _incident(client, severity="critical")
    _walk_to_risk(client, incident["id"])

    r = client.post(
        f"/api/incidents/{incident['id']}/transition",
        params={"new_status": "REMEDIATING"},
    )
    assert r.status_code == 403, r.text
    assert r.json()["detail"].startswith("risk level")


def test_unknown_risk_denies_remediation(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'g.db'}")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()

    with pytest.raises(gate.GateViolation, match="CRITICAL"):
        gate.assert_can_enter(db, "inc-none", IncidentStatus.REMEDIATING)


def test_low_risk_passes_without_approval(client):
    incident = _incident(client, severity="low")
    assessment = _walk_to_risk(
        client, incident["id"], context={"tests_available": "full"}
    )
    assert assessment["risk_level"] == "LOW"
    assert assessment["factors"]["score"] == 0

    r = client.post(
        f"/api/incidents/{incident['id']}/transition",
        params={"new_status": "REMEDIATING"},
    )
    assert r.status_code == 200, r.text


def test_rejected_approval_does_not_qualify(client):
    incident = _incident(client, severity="critical")
    _walk_to_risk(client, incident["id"])

    rejected = client.post(
        f"/api/incidents/{incident['id']}/approvals",
        json={"decision": "REJECTED", "reason": "too risky today"},
        headers=_auth(),
    )
    assert rejected.status_code == 201

    blocked = client.post(
        f"/api/incidents/{incident['id']}/transition",
        params={"new_status": "REMEDIATING"},
    )
    assert blocked.status_code == 403


# ── ledger obligation: risk is a prediction (CLAUDE.md 4) ───────────────────

def test_assess_risk_opens_ledger_prediction(client):
    incident = _incident(client, severity="high")
    r = client.post(f"/api/incidents/{incident['id']}/assess-risk", json={})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["risk_level"] in {level.value for level in RiskLevel}
    assert body["factors"]["rules"]

    db = next(app.dependency_overrides[get_db]())
    try:
        records = (
            db.query(OutcomeRecordDB)
            .filter(OutcomeRecordDB.incident_id == incident["id"])
            .all()
        )
        assert len(records) == 1
        assert records[0].prediction_type == "risk_level"
        assert records[0].status == "pending"
        assert records[0].components["score"] == body["factors"]["score"]
    finally:
        db.close()
