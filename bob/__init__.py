"""IBM Bob adapter -- the external engineering capability. Stage S4.

Bob is treated as a boundary, not a library (ARCHITECTURE.md section 16). BRE sends
task + relevant context + constraints + expected output + verification requirements;
Bob returns analysis. The write side (code changes, tests) belongs to S6 and is
gated; see adapter.BobAdapter.remediate.

Mechanism -- CONFIRMED (session 0005, closes thread 0001#7):

    bobide agent host -> local WebSocket JSON-RPC 2.0 server (AHP protocol),
    discovered through the CLI lockfile, authenticated by a connection token.
    recovery sources: bin/bobide --help, agent-host-stable.lock, and the
    method/param shapes in out/vs/workbench/workbench.desktop.main.js.

    Residual gap: the supervisor downloads a server build before listening, and
    IBM publishes no darwin archives (404 for darwin/*, 302 for linux/x64 and
    win32/x64). On this Mac a live host cannot start; the round trip is proven
    against tests/support/fake_bob_host.py, which implements the recovered
    protocol verbatim. First run on linux/x64 closes the last unknowns
    (default chat-channel encoding, turn-completion delivery) -- thread 0005#1.

Files:
    execution.py  Discovery (CLI probe, lockfile) + AgentHostClient.
    prompts.py    Task framing, constraints, output contract.
    adapter.py    BobAdapter.investigate / .diagnose, ledger cost capture.
                  .remediate / .verify raise until S6 / S7.

Obligations:
    - Capture token usage and wall time on EVERY call, into the outcome ledger.
      Cost cannot be reconstructed after the fact (ERRATA A8).
    - Until stage S6, nothing in this package may write to a target repository.
"""

from .adapter import BobAdapter, DiagnosisParseError
from .execution import (
    AgentHostAddress,
    AgentHostClient,
    BobError,
    BobHostUnavailable,
    BobNotInstalled,
    BobProtocolError,
    BobTurnTimeout,
    chat_channel_for,
    discover_agent_host,
    find_cli,
    probe_cli,
)

__all__ = [
    "AgentHostAddress",
    "AgentHostClient",
    "BobAdapter",
    "BobError",
    "BobHostUnavailable",
    "BobNotInstalled",
    "BobProtocolError",
    "BobTurnTimeout",
    "DiagnosisParseError",
    "chat_channel_for",
    "discover_agent_host",
    "find_cli",
    "probe_cli",
]
