"""Run a target repository's pytest suite and return structured per-test outcomes.

`connectors.tests.TestConnector` predates this and only extracts *failures*. Verification
needs more: how many ran, which passed, which errored, whether anything ran at all -- a
run that collected zero tests must never look like a pass.

Scopes (reliability/verification/__init__.py contract) are distinguishable in the result:

    TARGETED     the specific tests that were failing when the incident was investigated
    COMPONENT    the whole test files those tests live in, plus tests for changed modules
    REGRESSION   the entire suite

The runner never writes into the target repo: it disables the pytest cache and bytecode
so a verification run leaves `git status` exactly as it found it.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Sequence

DEFAULT_TIMEOUT_S = 180

_CASE_LINE = re.compile(r"^(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)\s+(\S+?)(?:\s+-\s+(.*))?$")
_SKIP_LINE = re.compile(r"^SKIPPED\s+\[\d+\]\s+(\S+?):\d+:\s*(.*)$")


class Scope(str, Enum):
    TARGETED = "targeted"
    COMPONENT = "component"
    REGRESSION = "regression"


@dataclass
class CaseResult:
    name: str
    outcome: str  # passed | failed | error | skipped | xfail | xpass
    message: Optional[str] = None

    @property
    def bad(self) -> bool:
        return self.outcome in ("failed", "error")


@dataclass
class RunResult:
    scope: Scope
    command: list[str]
    returncode: int
    cases: list[CaseResult] = field(default_factory=list)
    duration_ms: float = 0.0
    timed_out: bool = False
    tail: str = ""

    @property
    def passed(self) -> list[str]:
        return [c.name for c in self.cases if c.outcome == "passed"]

    @property
    def failing(self) -> set[str]:
        return {c.name for c in self.cases if c.bad}

    @property
    def ran(self) -> int:
        return sum(1 for c in self.cases if c.outcome in ("passed", "failed", "error", "xpass"))

    @property
    def ok(self) -> bool:
        """Green AND something actually ran. Zero collected tests is not a pass."""
        return self.returncode == 0 and not self.timed_out and self.ran > 0 and not self.failing

    def summary(self) -> dict:
        return {
            "scope": self.scope.value,
            "ok": self.ok,
            "ran": self.ran,
            "passed": len(self.passed),
            "failed": len(self.failing),
            "returncode": self.returncode,
            "timed_out": self.timed_out,
            "duration_ms": round(self.duration_ms, 1),
            "command": " ".join(self.command),
        }


def parse_pytest_report(output: str) -> list[CaseResult]:
    """Parse the `-rA` short-summary lines. Robust to a missing count line (which a
    `-qq` in the target's own addopts removes)."""
    cases: list[CaseResult] = []
    seen: set[tuple[str, str]] = set()
    for raw in output.splitlines():
        line = raw.strip()
        m = _CASE_LINE.match(line)
        if not m:
            continue
        kind, name, message = m.group(1), m.group(2), m.group(3)
        if kind == "SKIPPED" and _SKIP_LINE.match(line):
            skip = _SKIP_LINE.match(line)
            name, message = skip.group(1), skip.group(2)
        key = (kind, name)
        if key in seen:
            continue
        seen.add(key)
        cases.append(CaseResult(name=name, outcome=kind.lower(), message=message))
    return cases


class TestRunner:
    """Runs pytest in a subprocess. `__test__ = False` so pytest never collects it."""

    __test__ = False

    def __init__(self, *, python: str = sys.executable, timeout_s: int = DEFAULT_TIMEOUT_S) -> None:
        self.python = python
        self.timeout_s = timeout_s

    def command(self, selectors: Sequence[str] = ()) -> list[str]:
        return [
            self.python, "-m", "pytest",
            "-p", "no:cacheprovider",  # never write .pytest_cache into the target
            "-rA", "--tb=short", "--no-header",
            *selectors,
        ]

    def run(self, root: str | Path, scope: Scope, selectors: Sequence[str] = ()) -> RunResult:
        root = str(Path(root))
        cmd = self.command(selectors)
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"  # no __pycache__ in the target either
        env.pop("PYTEST_ADDOPTS", None)       # the caller's flags are not the target's
        started = time.perf_counter()
        try:
            proc = subprocess.run(
                cmd, cwd=root, capture_output=True, text=True,
                timeout=self.timeout_s, env=env, encoding="utf-8", errors="replace",
            )
        except subprocess.TimeoutExpired as exc:
            out = (exc.stdout or b"")
            out = out.decode("utf-8", "replace") if isinstance(out, bytes) else out
            return RunResult(scope, cmd, -1, [], (time.perf_counter() - started) * 1000,
                             timed_out=True, tail=out[-1500:])
        except OSError as exc:
            return RunResult(scope, cmd, 127, [], 0.0, tail=str(exc))
        combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
        return RunResult(
            scope=scope,
            command=cmd,
            returncode=proc.returncode,
            cases=parse_pytest_report(combined),
            duration_ms=(time.perf_counter() - started) * 1000,
            tail=combined[-1500:],
        )
