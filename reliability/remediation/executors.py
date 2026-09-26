"""The things that actually change files in a target repository.

`Executor.apply` is the write-path boundary. Exactly two implementations exist:

    BobShellExecutor   `bob run --mode agent` -- IBM Bob doing the engineering. THE product path.
    ReplayExecutor     applies a cassette's scripted edits. For CI and the credential-free demo;
                       only selected when BRE_BOB_TRANSPORT=replay, and labelled `simulated`.

Nothing here decides *whether* a write may happen. That is the engine's job (approval gate,
allowlist, checkpoint, branch-only, diff guard). An executor that is handed a repo root
simply does the work, so it must only ever be called from `RemediationEngine.run`.

`BobShellExecutor` contains the ONLY `allow_writes=True` in the codebase. It is asserted by
a test, so the write path stays grep-able rather than implicit.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Protocol

from bob.errors import BobError, BobNotAvailable
from bob.replay import ENV_VALUE as REPLAY, match_cassette
from bob.shell import BobShell
from bob.transport import ENV_TRANSPORT


@dataclass(frozen=True)
class ExecutorResult:
    summary: str
    tokens: int
    wall_ms: float
    provider: str
    meta: dict = field(default_factory=dict)

    @property
    def simulated(self) -> bool:
        return bool(self.meta.get("simulated"))


class Executor(Protocol):
    name: str

    def apply(self, prompt: str, *, repo_root: str) -> ExecutorResult: ...


class ExecutorError(BobError):
    """The executor could not do what was asked (bad edit, no cassette, non-success status)."""


class BobShellExecutor:
    name = "bob-shell"

    def __init__(
        self,
        *,
        binary: str = "bob",
        max_turns: Optional[int] = 40,
        max_cost: Optional[float] = None,
        timeout_s: int = 900,
    ) -> None:
        self.binary = binary
        self.max_turns = max_turns
        self.max_cost = max_cost
        self.timeout_s = timeout_s

    def apply(self, prompt: str, *, repo_root: str) -> ExecutorResult:
        shell = BobShell(
            repo_root, binary=self.binary, max_turns=self.max_turns,
            max_cost=self.max_cost, timeout_s=self.timeout_s,
        )
        result = shell.remediate(prompt, allow_writes=True)  # the only write authorisation in the repo
        if not result.ok:
            raise ExecutorError(
                f"bob run finished with status {result.status!r}: {result.last_message[:300]}"
            )
        return ExecutorResult(
            summary=result.last_message.strip(),
            tokens=result.usage.total_tokens,
            wall_ms=result.wall_ms,
            provider="bob-shell",
            meta={"task_id": result.task_id, "session_costs": result.usage.session_costs,
                  "tool_calls": result.usage.tool_calls},
        )


class ReplayExecutor:
    """Applies a cassette's edits: exact find/replace, each `find` must occur exactly once."""

    name = "replay"

    def apply(self, prompt: str, *, repo_root: str) -> ExecutorResult:
        cassette = match_cassette(repo_root)
        if cassette is None:
            raise ExecutorError(
                f"no recorded remediation matches the failure in {repo_root}; replay only answers "
                "scenarios it has a cassette for"
            )
        root = Path(repo_root).resolve()
        started = time.perf_counter()
        for edit in cassette.remediation["edits"]:
            target = (root / edit["file"]).resolve()
            if root not in target.parents:
                raise ExecutorError(f"cassette edit escapes the repository: {edit['file']}")
            # Bytes, not text: text mode would normalise a CRLF file to LF and turn a
            # one-line patch into a whole-file diff.
            text = target.read_bytes().decode("utf-8")
            if text.count(edit["find"]) != 1:
                raise ExecutorError(
                    f"{edit['file']}: expected exactly one occurrence of {edit['find']!r}, "
                    f"found {text.count(edit['find'])}"
                )
            target.write_bytes(text.replace(edit["find"], edit["replace"]).encode("utf-8"))
        return ExecutorResult(
            summary=cassette.remediation["summary"],
            tokens=int(cassette.remediation.get("usage_tokens", 0)),
            wall_ms=(time.perf_counter() - started) * 1000.0,
            provider="replay-bob",
            meta={"simulated": True, "scenario": cassette.scenario,
                  "usage_is_simulated": cassette.usage_is_simulated},
        )


def select_executor() -> Executor:
    """Bob Shell when usable; replay only when explicitly requested. Never silent simulation."""
    forced = os.environ.get(ENV_TRANSPORT, "").strip().lower()
    if forced == REPLAY:
        return ReplayExecutor()
    if forced == "host":
        raise BobNotAvailable(
            "the agent-host WebSocket transport is read-only; remediation needs Bob Shell (agent mode)"
        )
    preflight = BobShell(os.getcwd()).preflight()
    if not preflight.ready:
        raise BobNotAvailable(
            preflight.explain()
            + f"\n\nTo run the pipeline without Bob, set {ENV_TRANSPORT}={REPLAY} "
            "(results are labelled simulated)."
        )
    return BobShellExecutor()
