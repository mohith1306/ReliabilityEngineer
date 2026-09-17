"""Bob adapter contract tests.

The adapter is written against the documented Bob Shell CLI (session 0003). Bob is
not installed here, so these test everything that does not need a live Bob: argv
construction, result parsing against the documented stats block, and the write-path
guard. The live round trip is scripts/verify_bob.py and thread 0001#7.

If Bob's actual output differs from the documented schema, `test_parses_documented_
stats_block` is where that will surface first.
"""

import pytest

from bob.adapter import (
    BobAdapter,
    BobMode,
    BobNotAvailable,
    BobWriteRefused,
    parse_result,
)

# The schema documented at
# https://bob.ibm.com/docs/shell/getting-started/start-bobshell-non-interactive
DOCUMENTED_OUTPUT = {
    "type": "result",
    "timestamp": "2026-09-17T12:00:00Z",
    "status": "success",
    "stats": {
        "task_id": "task_abc123",
        "total_tokens": 14320,
        "input_tokens": 11200,
        "output_tokens": 3120,
        "cache_read_tokens": 8000,
        "cache_write_tokens": 1200,
        "cache_ratio": 0.56,
        "duration_ms": 8421,
        "session_costs": 0.42,
        "tool_calls": 7,
    },
    "last_message": "The models package holds the Pydantic domain contract.",
}


@pytest.fixture
def adapter(tmp_path):
    return BobAdapter(workspace=tmp_path, max_turns=5)


# ── result parsing ────────────────────────────────────────────────────────────

def test_parses_documented_stats_block():
    r = parse_result(DOCUMENTED_OUTPUT, mode=BobMode.ASK, wall_ms=9000.0)
    assert r.ok and r.status == "success"
    assert r.task_id == "task_abc123"
    assert r.usage.total_tokens == 14320
    assert r.usage.input_tokens == 11200
    assert r.usage.output_tokens == 3120
    assert r.usage.cache_read_tokens == 8000
    assert r.usage.session_costs == 0.42
    assert r.usage.tool_calls == 7
    assert r.usage.duration_ms == 8421
    assert r.wall_ms == 9000.0
    assert "Pydantic" in r.last_message


def test_cost_fields_are_what_the_outcome_ledger_needs():
    """ERRATA A8 is satisfied natively -- Bob reports its own cost."""
    r = parse_result(DOCUMENTED_OUTPUT, mode=BobMode.ASK, wall_ms=9000.0)
    assert r.usage.total_tokens > 0   # -> OutcomeRecord.cost_tokens
    assert r.usage.duration_ms > 0    # -> OutcomeRecord.cost_wall_ms


def test_error_status_is_not_ok():
    r = parse_result({"status": "error", "stats": {}}, mode=BobMode.ASK, wall_ms=1.0)
    assert not r.ok


def test_missing_stats_degrades_to_zero_not_a_crash():
    """A schema change must not take down an incident run."""
    r = parse_result({"status": "success"}, mode=BobMode.ASK, wall_ms=1.0)
    assert r.usage.total_tokens == 0
    assert r.task_id is None


def test_garbage_numeric_field_degrades_to_zero():
    """Zero is visibly wrong in the ledger. A guess is invisibly wrong."""
    payload = {"status": "success", "stats": {"total_tokens": "lots", "duration_ms": None}}
    r = parse_result(payload, mode=BobMode.ASK, wall_ms=1.0)
    assert r.usage.total_tokens == 0
    assert r.usage.duration_ms == 0.0


# ── argv construction ─────────────────────────────────────────────────────────

def test_command_shape(adapter, tmp_path):
    cmd = adapter.build_command(BobMode.ASK)
    assert cmd[:2] == ["bob", "run"]
    assert "--format" in cmd and cmd[cmd.index("--format") + 1] == "json"
    assert cmd[cmd.index("--mode") + 1] == "ask"
    assert cmd[cmd.index("--workspace") + 1] == str(tmp_path.resolve())
    assert cmd[cmd.index("--max-turns") + 1] == "5"


def test_loop_bounds_are_native(tmp_path):
    """ERRATA A4: Bob provides the termination bounds, we do not simulate them."""
    a = BobAdapter(workspace=tmp_path, max_turns=3, max_cost=1.5)
    cmd = a.build_command(BobMode.AGENT)
    assert cmd[cmd.index("--max-turns") + 1] == "3"
    assert cmd[cmd.index("--max-cost") + 1] == "1.5"


def test_blast_radius_narrowed_by_default(adapter):
    """MCP servers and subagents widen cost and blast radius unaccountably."""
    cmd = adapter.build_command(BobMode.ASK)
    assert "--disable-mcp" in cmd
    assert "--disable-subagents" in cmd


def test_resume_is_passed_through(adapter):
    """The reinvestigation loop continues a task rather than starting cold."""
    cmd = adapter.build_command(BobMode.ASK, resume="task_abc123")
    assert cmd[cmd.index("--resume") + 1] == "task_abc123"


def test_prompt_never_appears_in_argv(adapter):
    """Prompts go on stdin: argv is visible in process listings."""
    assert all("paragraph" not in part for part in adapter.build_command(BobMode.ASK))


# ── write-path guard ──────────────────────────────────────────────────────────

def test_only_agent_mode_is_a_write_path():
    assert not BobMode.ASK.is_write_path
    assert not BobMode.PLAN.is_write_path
    assert BobMode.AGENT.is_write_path


def test_remediate_refuses_without_explicit_authorisation(adapter):
    with pytest.raises(BobWriteRefused, match="allow_writes"):
        adapter.remediate("fix the failing test")


def test_read_paths_do_not_require_authorisation(adapter, monkeypatch):
    """They should fail on availability, not on the write guard."""
    monkeypatch.delenv("BOB_API_KEY", raising=False)
    for call in (adapter.investigate, adapter.diagnose, adapter.plan_remediation):
        with pytest.raises(BobNotAvailable):
            call("what does this do?")


# ── preflight ─────────────────────────────────────────────────────────────────

def test_preflight_reports_not_ready_when_bob_is_absent(tmp_path, monkeypatch):
    monkeypatch.delenv("BOB_API_KEY", raising=False)
    pre = BobAdapter(workspace=tmp_path, binary="definitely-not-a-real-binary").preflight()
    assert not pre.ready
    assert not pre.binary_found
    assert "not on PATH" in pre.explain()
    assert "BOB_API_KEY" in pre.explain()


def test_preflight_makes_no_billable_call(tmp_path, monkeypatch):
    """Preflight must be free -- it runs before every call."""
    monkeypatch.delenv("BOB_API_KEY", raising=False)
    called = []
    import bob.adapter as mod
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: called.append(a))
    BobAdapter(workspace=tmp_path, binary="definitely-not-a-real-binary").preflight()
    assert called == []
