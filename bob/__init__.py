"""IBM Bob adapter -- the external engineering capability. Stages S4 (read) and S6 (write).

Bob is treated as a boundary, not a library (ARCHITECTURE.md section 16). BRE sends
task + relevant context + constraints + expected output + verification requirements;
Bob returns analysis. BRE never reimplements a coding agent.

Two ways to reach Bob, with very different evidence behind them:

    shell.py       `bob run --format json --mode ask|plan|agent` -- Bob Shell, the
                   OFFICIALLY DOCUMENTED non-interactive surface (session 0007,
                   ADR-0004). Reports its own tokens and cost. The only surface with a
                   write path (agent mode). Contract read from the docs; NEVER YET RUN
                   against a live Bob -- `scripts/verify_bob.py` is the one command that
                   closes that (needs Bob Shell installed and BOB_API_KEY set).

    execution.py   The IDE's local agent-host WebSocket (JSON-RPC 2.0, "AHP"), recovered
                   by inspecting the shipped binaries (session 0005). UNDOCUMENTED, and
                   proven only against tests/support/fake_bob_host.py -- IBM publishes no
                   darwin host build, so it has never completed a real round trip.

    transport.py   `Transport` contract + both implementations + `select_transport()`,
                   which prefers Shell when `bob` is on PATH and BOB_API_KEY is set.
    adapter.py     `BobAdapter.investigate` / `.diagnose` -> `models.diagnosis.Diagnosis`,
                   transport-agnostic, with cost written to the outcome ledger.
    prompts.py     Task framing, constraints, output contract.
    errors.py      One exception root, `BobError`, for both surfaces.

Obligations:
    - Capture token usage and wall time on EVERY call, into the outcome ledger. Cost
      cannot be reconstructed after the fact (ERRATA A8).
    - `BobAdapter` (S4) is read-only. The only write path is `BobShell.remediate`, which
      refuses without `allow_writes=True` and is called solely by reliability/remediation
      behind the S5 approval gate and the S6 repository allowlist.
"""

from .adapter import BobAdapter, DiagnosisParseError
from .errors import (
    BobError,
    BobHostUnavailable,
    BobNotAvailable,
    BobNotInstalled,
    BobProtocolError,
    BobTurnTimeout,
    BobWriteRefused,
)
from .execution import (
    AgentHostAddress,
    AgentHostClient,
    chat_channel_for,
    discover_agent_host,
    find_cli,
    probe_cli,
)
from .shell import BobMode, BobPreflight, BobResult, BobShell, BobUsage, parse_result
from .transport import (
    AgentHostTransport,
    ShellTransport,
    Transport,
    TurnOutcome,
    select_transport,
)

__all__ = [
    "AgentHostAddress",
    "AgentHostClient",
    "AgentHostTransport",
    "BobAdapter",
    "BobError",
    "BobHostUnavailable",
    "BobMode",
    "BobNotAvailable",
    "BobNotInstalled",
    "BobPreflight",
    "BobProtocolError",
    "BobResult",
    "BobShell",
    "BobTurnTimeout",
    "BobUsage",
    "BobWriteRefused",
    "DiagnosisParseError",
    "ShellTransport",
    "Transport",
    "TurnOutcome",
    "chat_channel_for",
    "discover_agent_host",
    "find_cli",
    "parse_result",
    "probe_cli",
    "select_transport",
]
