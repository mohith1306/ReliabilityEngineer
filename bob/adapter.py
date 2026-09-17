"""IBM Bob adapter -- drives Bob Shell non-interactively.

Interface confirmed from the Bob Shell docs (session 0003), not assumed:

    bob run [options] [prompt...]           # prompt may also arrive on stdin
      --mode ask|plan|agent                 # read-only | read-only | WRITE PATH
      --format json|stream-json|pretty
      --workspace <path>                    # target repository root
      --max-turns <n>                       # native agentic-turn cap
      --max-cost <bobcoins>                 # native spend cap
      --resume <task-id> | --resume latest  # continue a prior task
      --disable-mcp / --disable-subagents / --disable-tool-groups <groups>
      --team-id <id>  --trust  --accept-license  --log-level <level>

    Auth: BOB_API_KEY in the environment (scope: Inference).
    Docs: https://bob.ibm.com/docs/shell/getting-started/start-bobshell-non-interactive

`--format json` emits one object whose `stats` block carries everything the outcome
ledger needs -- total/input/output/cache tokens, duration_ms, session_costs and
tool_calls -- so ERRATA A8 (no cost accounting) is satisfied natively rather than
by instrumenting around Bob.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

DEFAULT_BINARY = "bob"
DEFAULT_TIMEOUT_S = 900


class BobMode(str, Enum):
    """Bob Shell mode. ASK and PLAN cannot modify the workspace; AGENT can."""

    ASK = "ask"
    PLAN = "plan"
    AGENT = "agent"

    @property
    def is_write_path(self) -> bool:
        return self is BobMode.AGENT


class BobError(RuntimeError):
    """Bob could not be invoked, or returned something unusable."""


class BobNotAvailable(BobError):
    """Bob Shell is not installed, or is not authenticated."""


class BobWriteRefused(BobError):
    """An agent-mode call was attempted without an explicit write authorisation."""


@dataclass(frozen=True)
class BobUsage:
    """The cost of one Bob call. Maps straight onto OutcomeRecord cost fields."""

    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cache_ratio: float = 0.0
    session_costs: float = 0.0
    tool_calls: int = 0
    duration_ms: float = 0.0


@dataclass(frozen=True)
class BobResult:
    """One completed Bob session."""

    status: str
    mode: BobMode
    task_id: Optional[str]
    last_message: str
    usage: BobUsage
    wall_ms: float
    raw: dict = field(repr=False, default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "success"


def parse_result(payload: dict, *, mode: BobMode, wall_ms: float) -> BobResult:
    """Turn `bob run --format json` output into a BobResult.

    Tolerant of missing keys: Bob's stats block is documented but this must not
    explode on a version that adds or drops a field. A missing cost field becomes
    zero and is visible as zero in the ledger, which is honest -- unlike guessing.
    """
    stats = payload.get("stats") or {}

    def _num(key, cast, default):
        value = stats.get(key, default)
        try:
            return cast(value)
        except (TypeError, ValueError):
            return default

    usage = BobUsage(
        total_tokens=_num("total_tokens", int, 0),
        input_tokens=_num("input_tokens", int, 0),
        output_tokens=_num("output_tokens", int, 0),
        cache_read_tokens=_num("cache_read_tokens", int, 0),
        cache_write_tokens=_num("cache_write_tokens", int, 0),
        cache_ratio=_num("cache_ratio", float, 0.0),
        session_costs=_num("session_costs", float, 0.0),
        tool_calls=_num("tool_calls", int, 0),
        duration_ms=_num("duration_ms", float, 0.0),
    )
    return BobResult(
        status=str(payload.get("status", "error")),
        mode=mode,
        task_id=stats.get("task_id"),
        last_message=str(payload.get("last_message", "")),
        usage=usage,
        wall_ms=wall_ms,
        raw=payload,
    )


@dataclass
class BobPreflight:
    """Whether Bob can be called at all. Costs nothing and calls no model."""

    binary_found: bool
    binary_path: Optional[str]
    api_key_set: bool
    version: Optional[str] = None
    error: Optional[str] = None

    @property
    def ready(self) -> bool:
        return self.binary_found and self.api_key_set

    def explain(self) -> str:
        if self.ready:
            return f"Bob Shell ready: {self.binary_path} ({self.version or 'version unknown'})"
        problems = []
        if not self.binary_found:
            problems.append(
                "Bob Shell is not on PATH. Install it from "
                "https://bob.ibm.com/docs/shell/getting-started/install-and-setup"
            )
        if not self.api_key_set:
            problems.append(
                "BOB_API_KEY is not set. Create an API key with Scope=Inference in the "
                "Bob web portal, then set it in your environment. "
                "Never commit it, and never paste it into a prompt."
            )
        if self.error:
            problems.append(self.error)
        return "\n\n".join(problems)


class BobAdapter:
    """BRE boundary onto IBM Bob.

    BRE supplies task, context, constraints and verification requirements; Bob does
    the software engineering (ARCHITECTURE.md section 16). Nothing here reimplements
    a coding agent.

    Write safety: remediate() raises unless allow_writes=True is passed explicitly at
    the call site. Until stage S6 lands the approval gate, no caller in this repo may
    pass it. The flag exists so the write path is grep-able rather than implicit.
    """

    def __init__(
        self,
        workspace: str | Path,
        *,
        binary: str = DEFAULT_BINARY,
        max_turns: Optional[int] = 25,
        max_cost: Optional[float] = None,
        timeout_s: int = DEFAULT_TIMEOUT_S,
        team_id: Optional[str] = None,
        disable_mcp: bool = True,
        disable_subagents: bool = True,
    ) -> None:
        self.workspace = Path(workspace).resolve()
        self.binary = binary
        self.max_turns = max_turns
        self.max_cost = max_cost
        self.timeout_s = timeout_s
        self.team_id = team_id
        # Off by default: a reliability run should be reproducible, and MCP servers
        # or spawned subagents widen the blast radius and the cost envelope without
        # BRE being able to account for either.
        self.disable_mcp = disable_mcp
        self.disable_subagents = disable_subagents

    def preflight(self) -> BobPreflight:
        """Check Bob is installed and authenticated. Makes no billable call."""
        path = shutil.which(self.binary)
        api_key_set = bool(os.environ.get("BOB_API_KEY"))
        version = None
        error = None
        if path:
            try:
                proc = subprocess.run(
                    [path, "--version"], capture_output=True, text=True, timeout=30
                )
                version = (proc.stdout or proc.stderr).strip() or None
            except (subprocess.SubprocessError, OSError) as exc:
                error = f"bob --version failed: {exc}"
        return BobPreflight(
            binary_found=bool(path),
            binary_path=path,
            api_key_set=api_key_set,
            version=version,
            error=error,
        )

    # ── the four capabilities (ARCHITECTURE.md section 16) ────────────────────

    def investigate(self, prompt: str, **kw) -> BobResult:
        """Gather understanding. Read-only."""
        return self._run(BobMode.ASK, prompt, **kw)

    def diagnose(self, prompt: str, **kw) -> BobResult:
        """Root-cause analysis. Read-only.

        Present here although ARCHITECTURE.md section 16 omits it, because section 10
        assigns root-cause reasoning to Bob (ERRATA section B).
        """
        return self._run(BobMode.ASK, prompt, **kw)

    def plan_remediation(self, prompt: str, **kw) -> BobResult:
        """Propose a fix without applying it. Read-only."""
        return self._run(BobMode.PLAN, prompt, **kw)

    def remediate(self, prompt: str, *, allow_writes: bool = False, **kw) -> BobResult:
        """Apply a fix. THE WRITE PATH.

        Refuses unless allow_writes=True. The caller must have a passed approval
        gate; this class does not check for one, it only makes the write explicit.
        """
        if not allow_writes:
            raise BobWriteRefused(
                "remediate() is the write path and requires allow_writes=True. "
                "It must be called only behind a passed approval gate (stage S5). "
                "No caller in this repo is authorised to set it yet."
            )
        return self._run(BobMode.AGENT, prompt, **kw)

    # ── transport ─────────────────────────────────────────────────────────────

    def build_command(
        self,
        mode: BobMode,
        *,
        resume: Optional[str] = None,
        extra_args: Optional[list[str]] = None,
    ) -> list[str]:
        """The argv for one call. Split out from _run so it is testable offline."""
        cmd = [self.binary, "run", "--format", "json", "--mode", mode.value]
        cmd += ["--workspace", str(self.workspace)]
        if self.max_turns is not None:
            cmd += ["--max-turns", str(self.max_turns)]
        if self.max_cost is not None:
            cmd += ["--max-cost", str(self.max_cost)]
        if self.team_id:
            cmd += ["--team-id", self.team_id]
        if self.disable_mcp:
            cmd.append("--disable-mcp")
        if self.disable_subagents:
            cmd.append("--disable-subagents")
        if resume:
            cmd += ["--resume", resume]
        if extra_args:
            cmd += list(extra_args)
        return cmd

    def _run(
        self,
        mode: BobMode,
        prompt: str,
        *,
        resume: Optional[str] = None,
        extra_args: Optional[list[str]] = None,
    ) -> BobResult:
        pre = self.preflight()
        if not pre.ready:
            raise BobNotAvailable(pre.explain())

        cmd = self.build_command(mode, resume=resume, extra_args=extra_args)
        started = time.perf_counter()
        try:
            # Prompt goes on stdin, never in argv: it can be long, and argv is
            # visible in process listings.
            proc = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                cwd=str(self.workspace),
            )
        except subprocess.TimeoutExpired as exc:
            raise BobError(
                f"bob run timed out after {self.timeout_s}s in {mode.value} mode"
            ) from exc
        except OSError as exc:
            raise BobError(f"could not execute {cmd[0]}: {exc}") from exc
        wall_ms = (time.perf_counter() - started) * 1000

        if not proc.stdout.strip():
            raise BobError(
                f"bob run produced no stdout (exit {proc.returncode}). "
                f"stderr: {proc.stderr.strip()[:500]}"
            )
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise BobError(
                f"bob run did not emit valid JSON despite --format json: {exc}. "
                f"First 500 chars: {proc.stdout[:500]}"
            ) from exc

        return parse_result(payload, mode=mode, wall_ms=wall_ms)
