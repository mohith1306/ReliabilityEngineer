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

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Protocol

from bob.errors import BobError, BobNotAvailable
from bob.replay import ENV_VALUE as REPLAY, find_by_root_cause, match_cassette
from bob.recording import record_turn
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
        record_turn("remediation", prompt=prompt, response=result.last_message, tokens=result.usage.total_tokens,
                    wall_ms=result.wall_ms, provider="bob-shell", workspace=repo_root,
                    meta={"task_id": result.task_id, "usage": result.usage.__dict__})
        return ExecutorResult(
            summary=result.last_message.strip(),
            tokens=result.usage.total_tokens,
            wall_ms=result.wall_ms,
            provider="bob-shell",
            meta={"task_id": result.task_id, "session_costs": result.usage.session_costs,
                  "tool_calls": result.usage.tool_calls},
        )


_DIAGNOSIS_BLOCK = re.compile(
    r"DIAGNOSIS \(a hypothesis nobody has verified yet\):\n(\{.*?\n\})\n\nEVIDENCE:", re.DOTALL)


def _diagnosis_root_cause(prompt: str) -> Optional[str]:
    match = _DIAGNOSIS_BLOCK.search(prompt)
    if not match:
        return None
    try:
        return json.loads(match.group(1)).get("root_cause")
    except ValueError:
        return None


def _token_starts(text: str, find: str) -> list[int]:
    """Offsets where `find` occurs as a whole token, not glued to a longer word or number.

    `str.count` saw `pool_size: 2` inside `pool_size: 20`, so on the look-alike the seeded fix "applied" as
    20 -> 200 under the summary "Restore ... to 20", and the labelled when_misapplied path never ran.
    """
    pattern = re.escape(find)
    if re.match(r"\w", find[:1]):
        pattern = r"(?<!\w)" + pattern
    if re.match(r"\w", find[-1:]):
        pattern += r"(?!\w)"
    return [m.start() for m in re.finditer(pattern, text)]


class ReplayExecutor:
    """Applies a cassette's edits: exact find/replace, each `find` must occur exactly once.

    Like a real agent it FOLLOWS THE DIAGNOSIS IT IS GIVEN: the cassette is chosen by the diagnosis in
    the prompt, and only falls back to the repository's failure signature when the diagnosis is not a
    scripted one. If the diagnosed fix does not fit the repository (the value it would change is not
    there), the cassette's `when_misapplied` edit runs instead -- a plausible-but-wrong change, which
    is what an agent misled by a wrong diagnosis produces. Whether the result works is then decided by
    the test suite, not by this stand-in.
    """

    name = "replay"

    def apply(self, prompt: str, *, repo_root: str) -> ExecutorResult:
        root_cause = _diagnosis_root_cause(prompt)
        cassette = (find_by_root_cause(root_cause) if root_cause else None) or match_cassette(repo_root)
        if cassette is None:
            raise ExecutorError(
                f"no recorded remediation matches the diagnosis or the failure in {repo_root}; replay only "
                "answers scenarios it has a cassette for"
            )
        root = Path(repo_root).resolve()
        started = time.perf_counter()
        misapplied = False

        def path_of(rel: str) -> Path:
            target = (root / rel).resolve()
            if root not in target.parents:
                raise ExecutorError(f"cassette edit escapes the repository: {rel}")
            return target

        for edit in cassette.remediation["edits"]:
            target = path_of(edit["file"])
            # Bytes, not text: text mode would normalise a CRLF file to LF and turn a
            # one-line patch into a whole-file diff.
            text = target.read_bytes().decode("utf-8") if target.is_file() else ""
            starts = _token_starts(text, edit["find"])
            n = len(starts)
            if n == 1:
                at = starts[0]
                target.write_bytes((text[:at] + edit["replace"] + text[at + len(edit["find"]):]).encode("utf-8"))
                continue
            wrong = cassette.remediation.get("when_misapplied")
            if n == 0 and wrong:
                target = path_of(wrong["file"])
                text = target.read_bytes().decode("utf-8")
                changed, hits = re.subn(wrong["regex"], wrong["replace"], text, count=1)
                if hits:
                    target.write_bytes(changed.encode("utf-8"))
                    misapplied = True
                    continue
            raise ExecutorError(
                f"{edit['file']}: expected exactly one occurrence of {edit['find']!r}, found {n}"
            )
        return ExecutorResult(
            summary=cassette.remediation["summary"] + (" (applied to a repository it does not fit)" if misapplied else ""),
            tokens=int(cassette.remediation.get("usage_tokens", 0)),
            wall_ms=(time.perf_counter() - started) * 1000.0,
            provider="replay-bob",
            meta={"simulated": True, "scenario": cassette.scenario, "misapplied": misapplied,
                  "followed": "diagnosis" if root_cause and find_by_root_cause(root_cause) else "repo_signature",
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
