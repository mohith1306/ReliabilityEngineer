"""The reliability loop over HTTP -- the exact path the dashboard and the demo use.

Every request here goes through FastAPI and a real (temporary) SQLite file; the target repositories are
real git checkouts and the verification is real pytest. Only Bob is replaced, by its labelled replay
stand-in, and the system endpoint must say so.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.database import Base, get_db
from apps.api.main import app

KEY = "http-test-operator-key"
AUTH = {"Authorization": f"Bearer {KEY}"}


def build_client(tmp_path, monkeypatch, *, demo=True, show_key=True):
    monkeypatch.setenv("BRE_BOB_TRANSPORT", "replay")
    monkeypatch.setenv("BRE_OPERATOR_KEY", KEY)
    monkeypatch.setenv("BRE_OPERATOR_NAME", "Dana (http test)")
    monkeypatch.setenv("BRE_TAU", "0.30")
    monkeypatch.delenv("BRE_MAX_ATTEMPTS", raising=False)
    monkeypatch.delenv("BRE_REPO_ALLOWLIST", raising=False)
    monkeypatch.setenv("BRE_DEMO_DIR", str(tmp_path / "demo"))
    for name, on in (("BRE_DEMO", demo), ("BRE_DEMO_SHOW_KEY", show_key)):
        monkeypatch.setenv(name, "1") if on else monkeypatch.delenv(name, raising=False)
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    return engine


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = build_client(tmp_path, monkeypatch)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


def new_incident(client, scenario="seeded_failure"):
    r = client.post("/api/demo/incidents", json={"scenario": scenario})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def advance(client, incident_id):
    r = client.post(f"/api/incidents/{incident_id}/advance", json={})
    assert r.status_code == 200, r.text
    return r.json()


def approve(client, incident_id, headers=AUTH, **body):
    return client.post(f"/api/incidents/{incident_id}/approvals", headers=headers,
                       json={"decision": "APPROVED", "reason": "http test", **body})


# ── the system tells the truth about itself ────────────────────────────────────────────


def test_system_endpoint_says_bob_is_simulated_and_what_is_writable(client, tmp_path):
    s = client.get("/api/system").json()
    assert s["bob"]["simulated"] is True and s["bob"]["label"] == "SIMULATED BOB" and s["bob"]["mode"] == "replay"
    assert s["write_access"]["read_only"] is False
    assert [r.replace("\\", "/") for r in s["write_access"]["allowlisted_repositories"]] == [
        str((tmp_path / "demo").resolve()).replace("\\", "/")]  # exactly the demo workspace, nothing else
    assert s["tau"] == {"value": 0.3, "source": "env:BRE_TAU"} and s["max_attempts"] == 3


def test_the_operator_key_is_only_shown_when_the_demo_opted_in(tmp_path, monkeypatch):
    engine = build_client(tmp_path, monkeypatch, demo=True, show_key=False)
    try:
        with TestClient(app) as c:
            assert c.get("/api/system").json()["demo_operator_key"] is None
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_demo_endpoints_do_not_exist_when_demo_mode_is_off(tmp_path, monkeypatch):
    engine = build_client(tmp_path, monkeypatch, demo=False, show_key=False)
    try:
        with TestClient(app) as c:
            assert c.post("/api/demo/incidents", json={"scenario": "seeded_failure"}).status_code == 404
            assert c.get("/api/demo/scenarios").status_code == 404
            assert c.post("/api/demo/reset").status_code == 404
            s = c.get("/api/system").json()
            assert s["demo"] is False and s["write_access"]["read_only"] is True  # read-only unless allowlisted
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_the_dashboard_is_served_at_the_root(client):
    r = client.get("/")
    assert r.status_code == 200 and "Bob Reliability Engineer" in r.text and "text/html" in r.headers["content-type"]


# ── the whole lifecycle, over HTTP ───────────────────────────────────────────────────────


def test_full_lifecycle_over_http_with_an_authenticated_human_approval(client):
    iid = new_incident(client)

    first = advance(client, iid)
    assert first["status"] == "AWAITING_APPROVAL" and first["blocked_on"] == "approval"
    assert [s["action"] for s in first["steps"]] == ["investigate", "diagnose", "assess_risk", "request_approval"]

    # nothing is written until a human approves, and approving needs a real key
    assert client.post(f"/api/incidents/{iid}/approvals", json={"decision": "APPROVED"}).status_code == 401
    assert approve(client, iid, headers={"Authorization": "Bearer not-the-key"}).status_code == 401
    r = approve(client, iid, operator_name="Mallory", approved_by="Mallory", operator_id="forged")  # spoof attempts
    assert r.status_code == 201
    assert r.json()["operator_name"] == "Dana (http test)"  # identity comes from the key, never from the body

    second = advance(client, iid)
    assert second["status"] == "RESOLVED"
    assert [s["action"] for s in second["steps"]] == ["approved", "remediate", "verify"]

    d = client.get(f"/api/incidents/{iid}/detail").json()
    assert d["incident"]["status"] == "RESOLVED" and d["gate"] == {"risk_level": "HIGH", "approval_required": True, "satisfied": True}
    assert [e["to"] for e in d["timeline"] if e["kind"] == "transition"] == [
        "INVESTIGATING", "DIAGNOSED", "RISK_ASSESSED", "AWAITING_APPROVAL", "REMEDIATING", "VERIFYING", "RESOLVED"]
    assert {o["status"] for o in d["outcomes"]} == {"confirmed"} and all(o["verification_run_id"] for o in d["outcomes"])
    [ver] = d["verifications"]
    assert ver["status"] == "passed" and [k for k in ver["levels"] if k != "verdict"] == ["targeted", "component", "regression"]
    [rem] = d["remediations"]
    assert rem["changed_files"] == ["config/app.yaml"] and rem["branch"].startswith("bre/") and rem["executor"] == "replay"
    assert "repo_path" not in d["incident"]["metadata"]  # never leak a server filesystem path to the browser

    diff = client.get(f"/api/incidents/{iid}/remediations/{rem['id']}/diff").json()["diff"]
    assert "-  pool_size: 2" in diff and "+  pool_size: 20" in diff


def test_the_second_similar_incident_is_answered_from_memory_and_ownership_shows_it(client):
    first = new_incident(client)
    advance(client, first)
    approve(client, first)
    assert advance(client, first)["status"] == "RESOLVED"

    second = new_incident(client)
    advance(client, second)
    d = client.get(f"/api/incidents/{second}/detail").json()
    diag = [o for o in d["outcomes"] if o["type"] == "diagnosis"][0]
    routing = [o for o in d["outcomes"] if o["type"] == "routing"][0]
    assert (diag["predictor"], diag["cost_tokens"]) == ("memory", 0)
    assert routing["components"]["action"] == "ROUTE" and "tau 0.30" in routing["components"]["reason"]

    own = client.get("/api/ownership").json()
    assert {(s["source"], s["topic"]) for s in own["standings"]} == {("bob", "database")}  # memory has not been verified yet
    assert len(own["memory"]) == 1 and own["memory"][0]["source"] == "bob"


def test_a_lookalike_is_refuted_over_http_and_the_incident_recovers(client):
    """Seed memory with the config-regression fix, then hand it the look-alike whose cause is in code."""
    a = new_incident(client, "seeded_failure")
    advance(client, a)
    approve(client, a)
    assert advance(client, a)["status"] == "RESOLVED"

    b = new_incident(client, "connection_cap")
    res = advance(client, b)
    assert res["blocked_on"] == "approval"
    approve(client, b)
    res = advance(client, b)  # attempt 1: memory's fix is applied, tests still fail, verification refutes it
    assert res["steps"][2]["action"] == "verify" and res["steps"][2]["data"]["passed"] is False
    d = client.get(f"/api/incidents/{b}/detail").json()
    assert d["incident"]["attempt"] == 2 and d["incident"]["status"] == "AWAITING_APPROVAL"
    first_diag = [o for o in d["outcomes"] if o["type"] == "diagnosis" and o["attempt"] == 1][0]
    assert (first_diag["predictor"], first_diag["status"]) == ("memory", "refuted")
    assert d["remediations"][0]["status"] == "rolled_back"

    approve(client, b)  # a new assessment needs a NEW approval
    assert advance(client, b)["status"] == "RESOLVED"  # attempt 2: a full investigation finds the cap in code
    d = client.get(f"/api/incidents/{b}/detail").json()
    assert [o["predictor"] for o in d["outcomes"] if o["type"] == "diagnosis"] == ["memory", "bob-adapter"]


def test_advance_on_an_unknown_incident_is_404(client):
    assert client.post("/api/incidents/nope/advance", json={}).status_code == 404
    assert client.get("/api/incidents/nope/detail").status_code == 404


# ── the demo reset cannot wipe anything BRE did not make ───────────────────────────────────


def test_reset_only_deletes_a_workspace_that_bre_itself_marked(tmp_path, monkeypatch):
    engine = build_client(tmp_path, monkeypatch)
    precious = tmp_path / "demo"          # BRE_DEMO_DIR points at a directory BRE never created
    precious.mkdir()
    (precious / "important.txt").write_text("do not delete", encoding="utf-8")
    try:
        with TestClient(app) as c:
            assert c.post("/api/demo/reset").json() == {"reset": True}
            assert (precious / "important.txt").exists(), "an unmarked directory must survive a reset"
            new_incident(c)  # BRE now marks the workspace it uses...
            assert (precious / ".bre-demo-workspace").is_file()
            c.post("/api/demo/reset")
            assert not precious.exists()  # ...and only then may a reset remove it
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_results_endpoint_lists_stamped_comparisons(client):
    r = client.get("/api/results")
    assert r.status_code == 200 and isinstance(r.json()["slices"], list)
    for s in r.json()["slices"]:
        assert s["artifact"].startswith("comparison_") and "aggregate" in s
