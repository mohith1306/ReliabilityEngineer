"""How one read-only Bob turn actually reaches Bob.

Two transports behind one contract, `Transport.run(prompt, working_directory=...)`:

    ShellTransport       `bob run --mode ask` -- the officially documented surface.
                         Reports its own tokens and cost. PREFERRED.
    AgentHostTransport   JSON-RPC over the IDE's local agent-host WebSocket, recovered
                         from the shipped binaries (session 0005). Undocumented, and it
                         has never completed a round trip against a real host -- it is
                         proven only against tests/support/fake_bob_host.py.

`BobAdapter` (bob/adapter.py) owns prompts, diagnosis parsing and the outcome ledger;
it does not care which transport carried the turn.

Both transports are READ-ONLY: Shell is pinned to `ask` mode, and the write path
(`agent` mode) is reachable only through `BobShell.remediate`, behind the S5 gate.
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from .errors import BobError, BobHostUnavailable, BobNotAvailable, BobNotInstalled, BobTurnTimeout
from .execution import (
    DEFAULT_TURN_TIMEOUT,
    AgentHostClient,
    AgentHostAddress,
    chat_channel_for,
    discover_agent_host,
)
from .recording import record_turn
from .shell import BobShell

DEFAULT_PROVIDER = "copilot"
ENV_TRANSPORT = "BRE_BOB_TRANSPORT"  # "shell" | "host" | "replay" (never automatic) | unset for auto


@dataclass(frozen=True)
class TurnOutcome:
    """One completed read-only turn, in transport-neutral form."""

    text: str
    tokens: int
    wall_ms: float
    provider: str
    turn_id: str
    extra: dict = field(default_factory=dict)


class Transport(Protocol):
    name: str

    def run(self, prompt: str, *, working_directory: Optional[str] = None) -> TurnOutcome: ...


class ShellTransport:
    """`bob run --format json --mode ask` -- documented, cost-reporting, read-only."""

    name = "shell"

    def __init__(
        self,
        *,
        binary: str = "bob",
        max_turns: Optional[int] = 25,
        max_cost: Optional[float] = None,
        timeout_s: int = 900,
    ) -> None:
        self.binary = binary
        self.max_turns = max_turns
        self.max_cost = max_cost
        self.timeout_s = timeout_s

    def run(self, prompt: str, *, working_directory: Optional[str] = None) -> TurnOutcome:
        shell = BobShell(
            working_directory or os.getcwd(),
            binary=self.binary,
            max_turns=self.max_turns,
            max_cost=self.max_cost,
            timeout_s=self.timeout_s,
        )
        result = shell.diagnose(prompt)  # ASK mode: cannot modify the workspace
        if not result.ok:
            raise BobError(
                f"bob run finished with status {result.status!r}: {result.last_message[:300]}"
            )
        record_turn("diagnosis", prompt=prompt, response=result.last_message, tokens=result.usage.total_tokens,
                    wall_ms=result.wall_ms, provider="bob-shell", workspace=working_directory,
                    meta={"task_id": result.task_id, "usage": result.usage.__dict__})
        return TurnOutcome(
            text=result.last_message,
            tokens=result.usage.total_tokens,
            wall_ms=result.wall_ms,
            provider="bob-shell",
            turn_id=result.task_id or "",
            extra={"session_costs": result.usage.session_costs, "tool_calls": result.usage.tool_calls},
        )


class AgentHostTransport:
    """Experimental: AHP JSON-RPC over the agent-host WebSocket."""

    name = "host"

    def __init__(
        self,
        address: Optional[str] = None,
        *,
        provider: str = DEFAULT_PROVIDER,
        turn_timeout: float = DEFAULT_TURN_TIMEOUT,
    ) -> None:
        self.address = address
        self.provider = provider
        self.turn_timeout = turn_timeout

    def run(self, prompt: str, *, working_directory: Optional[str] = None) -> TurnOutcome:
        address: AgentHostAddress = discover_agent_host(self.address)
        started = time.perf_counter()

        with AgentHostClient(address) as client:
            client.initialize()
            session_uri = f"{self.provider}:/{uuid.uuid4()}"
            client.create_session(session_uri, self.provider, working_directory=working_directory)
            chat_uri = chat_channel_for(session_uri)
            client.create_chat(session_uri, chat_uri)
            client.subscribe(session_uri)

            turn_id = str(uuid.uuid4())
            message = {"text": prompt, "origin": {"kind": "user"}}
            client.dispatch_action(chat_uri, {
                "type": "chat/pendingMessageSet",
                "kind": "queued",
                "id": turn_id,
                "message": message,
            }, client_seq=1)
            client.dispatch_action(chat_uri, {
                "type": "chat/turnStarted",
                "turnId": turn_id,
                "message": message,
            }, client_seq=2)

            completion = client.wait_for_notification(
                _is_turn_completion,
                timeout=self.turn_timeout,
                label=f"turn {turn_id} completion",
            )
            client.unsubscribe(chat_uri)

        wall_ms = (time.perf_counter() - started) * 1000.0
        turn = _extract_turn(completion)
        usage = turn.get("usage") or {}
        tokens = int(usage.get("promptTokens", 0) or 0) + int(usage.get("completionTokens", 0) or 0)
        return TurnOutcome(
            text=_turn_text(turn),
            tokens=tokens,
            wall_ms=wall_ms,
            provider=self.provider,
            turn_id=turn_id,
        )


def select_transport(*, turn_timeout: float = DEFAULT_TURN_TIMEOUT) -> Transport:
    """Pick a transport from the environment. Shell wins when it is usable.

    BRE_BOB_TRANSPORT=shell|host forces one. Otherwise: Bob Shell if `bob` is on PATH and
    BOB_API_KEY is set; else a running agent host; else BobNotAvailable explaining both.
    """
    forced = os.environ.get(ENV_TRANSPORT, "").strip().lower()
    if forced == "replay":
        from .replay import ReplayTransport  # lazy: replay imports this module

        return ReplayTransport()
    if forced == "shell":
        return ShellTransport()
    if forced == "host":
        return AgentHostTransport(turn_timeout=turn_timeout)

    preflight = BobShell(os.getcwd()).preflight()
    if preflight.ready:
        return ShellTransport()
    try:
        discover_agent_host()
    except (BobHostUnavailable, BobNotInstalled) as exc:
        raise BobNotAvailable(
            f"{preflight.explain()}\n\nNo agent host is running either ({exc})."
        ) from exc
    return AgentHostTransport(turn_timeout=turn_timeout)


# ── agent-host reply shaping (moved verbatim from the old adapter) ───────────


def _is_turn_completion(msg: dict) -> bool:
    params = msg.get("params") or {}
    for found in _walk(params):
        if not isinstance(found, dict):
            continue
        status = str(found.get("status", "")).lower()
        if status in ("completed", "complete", "done") and (
            "usage" in found or "responseParts" in found
        ):
            return True
        if "usage" in found and ("responseParts" in found or "text" in found):
            return True
    action = params.get("action") or {}
    if action.get("type") == "chat/turnCancelled":
        raise BobTurnTimeout(f"turn cancelled by host: {action}")
    return False


def _walk(value: Any):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _extract_turn(msg: dict) -> dict:
    params = msg.get("params") or {}
    for found in _walk(params):
        if isinstance(found, dict) and ("usage" in found or "responseParts" in found):
            if "text" not in found and "responseParts" not in found and "usage" not in found:
                continue
            return found
    snapshot = params.get("snapshot") or {}
    for found in _walk(snapshot):
        if isinstance(found, dict) and ("usage" in found or "responseParts" in found):
            return found
    return params


def _turn_text(turn: dict) -> str:
    if isinstance(turn.get("text"), str):
        return turn["text"]
    parts = turn.get("responseParts") or []
    chunks = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        for key in ("text", "content", "value"):
            if isinstance(part.get(key), str):
                chunks.append(part[key])
                break
    return "\n".join(chunks)
