"""Recording live Bob output: opt-in, never into the repository under repair, never a secret."""

from __future__ import annotations

import json

import pytest

from bob import recording
from bob.recording import RecordingRefused, record_turn
from bob.shell import BobMode, BobResult, BobUsage
from bob.transport import ShellTransport


def turn(**kw):
    base = dict(prompt="diagnose this", response='{"root_cause": "x"}', tokens=123, wall_ms=45.6, provider="bob-shell")
    base.update(kw)
    return record_turn("diagnosis", **base)


def test_off_by_default_nothing_is_written(tmp_path, monkeypatch):
    monkeypatch.delenv("BRE_BOB_RECORD_DIR", raising=False)
    assert turn() is None


def test_records_the_turn_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("BRE_BOB_RECORD_DIR", str(tmp_path / "rec"))
    path = turn(meta={"task_id": "t1"})
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["recorded_from_live_bob"] is True and data["kind"] == "diagnosis"
    assert data["prompt"] == "diagnose this" and data["response"] == '{"root_cause": "x"}'
    assert data["tokens"] == 123 and data["meta"] == {"task_id": "t1"}
    assert len(data["prompt_sha256"]) == 64


def test_a_replay_turn_is_never_marked_as_live(tmp_path, monkeypatch):
    monkeypatch.setenv("BRE_BOB_RECORD_DIR", str(tmp_path))
    data = json.loads(turn(provider="replay-bob").read_text(encoding="utf-8"))
    assert data["recorded_from_live_bob"] is False


def test_refuses_to_record_inside_the_repository_under_repair(tmp_path, monkeypatch):
    repo = tmp_path / "target"
    repo.mkdir()
    monkeypatch.setenv("BRE_BOB_RECORD_DIR", str(repo / "recordings"))
    with pytest.raises(RecordingRefused):
        turn(workspace=str(repo))
    monkeypatch.setenv("BRE_BOB_RECORD_DIR", str(repo))
    with pytest.raises(RecordingRefused):
        turn(workspace=str(repo))
    assert not (repo / "recordings").exists()


def test_the_api_key_never_reaches_a_recording(tmp_path, monkeypatch):
    monkeypatch.setenv("BOB_API_KEY", "super-secret-bob-key-0123456789")
    monkeypatch.setenv("BRE_BOB_RECORD_DIR", str(tmp_path))
    text = turn().read_text(encoding="utf-8")
    assert "super-secret-bob-key" not in text


def test_the_shell_transport_records_what_bob_said(tmp_path, monkeypatch):
    monkeypatch.setenv("BRE_BOB_RECORD_DIR", str(tmp_path / "rec"))
    result = BobResult(status="success", mode=BobMode.ASK, task_id="task_9", last_message='{"root_cause": "y"}',
                       usage=BobUsage(total_tokens=777, session_costs=0.31, tool_calls=2), wall_ms=12.0)
    monkeypatch.setattr("bob.transport.BobShell.diagnose", lambda self, prompt, **kw: result)
    outcome = ShellTransport().run("what broke?", working_directory=str(tmp_path / "repo"))
    assert outcome.tokens == 777 and outcome.provider == "bob-shell"
    [rec] = (tmp_path / "rec").glob("*.json")
    data = json.loads(rec.read_text(encoding="utf-8"))
    assert data["tokens"] == 777 and data["meta"]["task_id"] == "task_9" and data["meta"]["usage"]["session_costs"] == 0.31
