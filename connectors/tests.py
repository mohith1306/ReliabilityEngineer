"""Test discovery and execution. READ-ONLY with respect to the target repo.

Discovery reads the tree; execution runs the target's existing test command
in a subprocess. Neither writes into the target repository.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .repository import RepositoryConnector

TEST_FILE_PATTERNS = (
    re.compile(r"(^|/)test_[^/]+$"),
    re.compile(r"(^|/)[^/]+_test$"),
    re.compile(r"(^|/)tests?/.*\.(py|js|ts|go|rb)$"),
)

TEST_NAME_PATTERN = re.compile(r"^\s*(?:def|function|func)\s+(test_\w+)", re.MULTILINE)

COMMAND_TIMEOUT_SECONDS = 120


@dataclass
class DiscoveredTest:
    file: str
    name: str | None = None


@dataclass
class TestCaseResult:
    name: str
    passed: bool
    error: str | None = None


@dataclass
class TestRunResult:
    command: str
    returncode: int
    passed: bool
    cases: list[TestCaseResult] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    truncated: bool = False


class TestConnector:
    """Discovers tests in a repo and runs a scope, returning structured results."""

    __test__ = False  # not a pytest test class -- pytest must not collect it

    def __init__(self, repository: RepositoryConnector | None = None) -> None:
        self._repository = repository or RepositoryConnector()

    def discover(self, root: str) -> list[DiscoveredTest]:
        tests: list[DiscoveredTest] = []
        for sf in self._repository.list_files(root):
            is_test_file = any(p.search(sf.path) for p in TEST_FILE_PATTERNS)
            if not is_test_file:
                continue
            try:
                text = self._repository.read_file(root, sf.path)
            except (OSError, ValueError):
                continue
            names = TEST_NAME_PATTERN.findall(text)
            if names:
                for n in names:
                    tests.append(DiscoveredTest(file=sf.path, name=n))
            else:
                tests.append(DiscoveredTest(file=sf.path))
        return tests

    def run(self, root: str, args: list[str] | None = None, *, cwd: str | None = None) -> TestRunResult:
        """Run a test command in the target repo. Defaults to `python -m pytest -q`."""
        if args is None:
            args = [sys.executable, "-m", "pytest", "-q", "--no-header"]
        workdir = cwd or root
        cmd_display = " ".join(args)
        try:
            proc = subprocess.run(
                args, cwd=workdir, capture_output=True, text=True,
                timeout=COMMAND_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return TestRunResult(
                command=cmd_display, returncode=-1, passed=False,
                stderr=f"timed out after {COMMAND_TIMEOUT_SECONDS}s",
            )
        except FileNotFoundError as exc:
            return TestRunResult(
                command=cmd_display, returncode=-1, passed=False, stderr=str(exc),
            )

        combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
        cases = _parse_pytest_output(combined)
        return TestRunResult(
            command=cmd_display,
            returncode=proc.returncode,
            passed=proc.returncode == 0,
            cases=cases,
            stdout=(proc.stdout or "")[:8000],
            stderr=(proc.stderr or "")[:8000],
            truncated=len(combined) > 8000,
        )


def _parse_pytest_output(output: str) -> list[TestCaseResult]:
    """Best-effort parse of pytest -q output into per-case results.

    pytest -q prints a short summary line (`1 failed, 2 passed`) and, on
    failure, `FAILED path::test_name - message`. We parse the FAILED lines
    and infer passes from the count line when individual names are absent.
    """
    cases: list[TestCaseResult] = []
    failed_names: set[str] = set()
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("FAILED "):
            # "FAILED tests/x.py::test_y - AssertionError..."
            body = line[len("FAILED "):]
            name = body.split(" - ")[0].strip()
            reason = body.split(" - ", 1)[1].strip() if " - " in body else "failed"
            cases.append(TestCaseResult(name=name, passed=False, error=reason))
            failed_names.add(name)

    summary = re.search(r"(\d+) failed(?:, (\d+) passed)?", output)
    if summary and not cases:
        n_failed = int(summary.group(1))
        for i in range(n_failed):
            cases.append(TestCaseResult(name=f"unknown_failure_{i}", passed=False, error="see output"))
    elif summary:
        n_failed = int(summary.group(1))
        if n_failed > len(failed_names):
            for i in range(n_failed - len(failed_names)):
                cases.append(TestCaseResult(name=f"unknown_failure_{i}", passed=False, error="see output"))

    return cases
