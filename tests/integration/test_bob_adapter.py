"""Bob adapter end to end (S4 exit criteria).

    - the real Bob interface is confirmed by a working call (probe_cli hits the
      installed bobide binary; discovery parses the real lockfile format)
    - BobAdapter.investigate() and .diagnose() return a models/diagnosis.Diagnosis
    - token usage + wall time land in the outcome ledger on every call
    - nothing in bob/ can write to a target repository
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.database import Base
from bob import (
    AgentHostClient,
    BobAdapter,
    BobHostUnavailable,
    BobTurnTimeout,
    chat_channel_for,
    discover_agent_host,
    find_cli,
    probe_cli,
)
from models.diagnosis import Diagnosis
from models.outcome import OutcomeStatus, PredictionType
from tests.support.fake_bob_host import (
    DEFAULT_COMPLETION_TOKENS,
    DEFAULT_PROMPT_TOKENS,
    FakeBobHost,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
BOB_SOURCES = sorted((REPO_ROOT / "bob").glob("*.py"))

ASSISTANT_JSON = json.dumps({
    "root_cause": "config/auth.yaml lowered request_timeout_seconds to 0.001 "
                  "while the auth backend latency is 0.05s.",
    "confidence": 0.86,
    "affected_components": ["authservice.py", "config/auth.yaml"],
    "evidence_ids": ["tests/test_authservice.py::test_login_within_timeout"],
    "assumptions": ["backend latency is stable at ~50ms"],
    "unresolved_uncertainty": ["whether retry logic exists upstream"],
})

EVIDENCE = [
    {"source_type": "test",
     "source_reference": "tests/test_authservice.py::test_login_within_timeout",
     "content": "RequestTimeoutError: login request timed out after 0.001s",
     "relevance_score": 0.95, "confidence": 0.9},
    {"source_type": "repository",
     "source_reference": "config/auth.yaml",
     "content": "request_timeout_seconds: 0.001",
     "relevance_score": 0.9, "confidence": 0.9},
    {"source_type": "ci",
     "source_reference": "ci/failure.log::tests/test_authservice.py",
     "content": "FAILED tests/test_authservice.py::test_login_within_timeout",
     "relevance_score": 0.8, "confidence": 0.8},
]

INCIDENT = {"id": "inc-bob-1", "type": "test_failure", "severity": "high",
            "description": "auth login timeout"}


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def fake_host():
    host = FakeBobHost(ASSISTANT_JSON)
    host.start()
    yield host
    host.stop()


# -- criterion 1: confirmed by a real call ---------------------------------

def test_probe_cli_calls_the_installed_bob_binary():
    if find_cli() is None:
        pytest.skip("no bobide binary on this machine")
    result = probe_cli()
    assert result["banner"].startswith("IBM Bob")
    assert result["version"]
    assert Path(result["cli"]).exists()


def test_discovery_parses_the_real_lockfile_format(tmp_path, monkeypatch):
    lock = {
        "schemaVersion": 1, "pid": os.getpid(), "port": 45678,
        "host": "127.0.0.1", "connectionToken": "tok-abc",
        "protocolVersion": "0.1.0", "quality": "stable",
    }
    (tmp_path / "agent-host-stable.lock").write_text(json.dumps(lock))
    monkeypatch.setenv("VSCODE_CLI_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("BOB_AGENT_HOST", raising=False)

    address = discover_agent_host()
    assert address.port == 45678
    assert address.token == "tok-abc"
    assert address.url == "ws://127.0.0.1:45678?tkn=tok-abc"
    assert address.pid_alive()


def test_discovery_prefers_explicit_url(monkeypatch):
    monkeypatch.delenv("BOB_AGENT_HOST", raising=False)
    address = discover_agent_host("ws://127.0.0.1:9911?tkn=zzz")
    assert address.url == "ws://127.0.0.1:9911?tkn=zzz"


def test_discovery_raises_when_no_host_runs(tmp_path, monkeypatch):
    monkeypatch.delenv("BOB_AGENT_HOST", raising=False)
    monkeypatch.setenv("VSCODE_CLI_DATA_DIR", str(tmp_path / "empty"))
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(BobHostUnavailable, match="no live agent host"):
        discover_agent_host()


# -- protocol round trip over real sockets ---------------------------------

def test_initialize_list_and_session_lifecycle(fake_host):
    with AgentHostClient(fake_host.address) as client:
        init = client.initialize()
        assert init["serverSeq"] == 1
        assert client.list_sessions() == []
        session_uri = "copilot:/11111111-2222-3333-4444-555555555555"
        client.create_session(session_uri, "copilot", working_directory="/tmp")
        chat_uri = chat_channel_for(session_uri)
        assert chat_uri.startswith("ahp-chat://default/")
        client.create_chat(session_uri, chat_uri)
        client.subscribe(session_uri)
        client.dispatch_action(chat_uri, {
            "type": "chat/turnStarted", "turnId": "t1",
            "message": {"text": "hi", "origin": {"kind": "user"}},
        }, client_seq=1)
        done = client.wait_for_notification(
            lambda m: (m.get("params") or {}).get("channel") == chat_uri
            and "snapshot" in (m.get("params") or {}),
            timeout=5, label="snapshot",
        )
        assert done["params"]["snapshot"]["activeTurn"]["status"] == "completed"

    assert fake_host.methods() == [
        "initialize", "listSessions", "createSession", "createChat", "subscribe",
    ]


# -- criteria 2 + 3: structured Diagnosis and ledger cost -------------------

def test_investigate_returns_diagnosis_and_writes_ledger(fake_host, db):
    adapter = BobAdapter(db, address=fake_host.url, topic="auth")
    diagnosis = adapter.investigate(INCIDENT, EVIDENCE)

    assert isinstance(diagnosis, Diagnosis)
    assert diagnosis.root_cause.startswith("config/auth.yaml")
    assert diagnosis.confidence == 0.86
    assert diagnosis.affected_components == ["authservice.py", "config/auth.yaml"]
    assert diagnosis.evidence_ids
    assert diagnosis.assumptions

    from reliability.ledger.query import cost_rollup
    from reliability.ledger.record import OutcomeLedger

    rollup = cost_rollup(db)
    assert rollup["total_tokens"] == DEFAULT_PROMPT_TOKENS + DEFAULT_COMPLETION_TOKENS
    assert rollup["total_wall_ms"] > 0

    records = OutcomeLedger(db).pending_for_incident("inc-bob-1")
    assert len(records) == 1
    record = records[0]
    assert record.status is OutcomeStatus.PENDING
    assert record.predictor_id == "bob-adapter"
    assert record.prediction_type is PredictionType.DIAGNOSIS
    assert record.cost_tokens == DEFAULT_PROMPT_TOKENS + DEFAULT_COMPLETION_TOKENS
    assert record.components["evidence_count"] == len(EVIDENCE)
    assert record.components["prompt_sha256"]


def test_diagnose_returns_diagnosis(fake_host, db):
    adapter = BobAdapter(db, address=fake_host.url, topic="auth")
    diagnosis = adapter.diagnose(INCIDENT, EVIDENCE)
    assert isinstance(diagnosis, Diagnosis)
    assert diagnosis.unresolved_uncertainty


def test_turn_timeout_is_typed(fake_host, db):
    fake_host.assistant_text = ASSISTANT_JSON
    original = fake_host._route_notification
    fake_host._route_notification = lambda *a, **k: None  # swallow turn
    try:
        adapter = BobAdapter(db, address=fake_host.url, turn_timeout=0.3)
        with pytest.raises(BobTurnTimeout):
            adapter.investigate(INCIDENT, EVIDENCE)
    finally:
        fake_host._route_notification = original


# -- criterion 4: no write path --------------------------------------------

def test_remediate_and_verify_refuse_to_act(fake_host, db):
    adapter = BobAdapter(db, address=fake_host.url)
    with pytest.raises(NotImplementedError, match="approval gate"):
        adapter.remediate()
    with pytest.raises(NotImplementedError, match="S7"):
        adapter.verify()


def test_adapter_leaves_target_repo_untouched(tmp_path, fake_host, db):
    repo = tmp_path / "target"
    repo.mkdir()
    (repo / "app.py").write_text("x = 1\n")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-qm", "init"],
        cwd=repo, check=True,
    )

    before = sorted(
        (p.relative_to(repo).as_posix(), p.read_bytes())
        for p in repo.rglob("*") if p.is_file() and ".git" not in p.parts
    )
    status_before = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo,
        capture_output=True, text=True, check=True,
    ).stdout

    adapter = BobAdapter(db, address=fake_host.url, topic="auth")
    adapter.investigate(INCIDENT, EVIDENCE, working_directory=str(repo))

    after = sorted(
        (p.relative_to(repo).as_posix(), p.read_bytes())
        for p in repo.rglob("*") if p.is_file() and ".git" not in p.parts
    )
    status_after = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo,
        capture_output=True, text=True, check=True,
    ).stdout
    assert before == after
    assert status_before == status_after == ""


def test_bob_sources_contain_no_write_apis():
    forbidden = (
        "write_text", "write_bytes", "shutil.copy", "shutil.move",
        "os.remove", "os.rename", ".unlink(", "git commit", "apply_patch",
        "Path.touch",
    )
    for path in BOB_SOURCES:
        source = path.read_text()
        for marker in forbidden:
            assert marker not in source, f"{path.name} contains {marker!r}"


def test_public_surface_is_read_only():
    read_only = {"investigate", "diagnose"}
    adapter = BobAdapter(None)
    public = {name for name in dir(adapter) if not name.startswith("_")}
    writable = public - read_only - {
        "db", "address", "provider", "topic", "turn_timeout", "transport",
        "remediate", "verify",
    }
    assert not writable, f"unexpected public surface: {writable}"
    for stub in ("remediate", "verify"):
        with pytest.raises(NotImplementedError):
            getattr(adapter, stub)()
