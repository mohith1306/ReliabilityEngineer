"""Reject patches that turn a red suite green by weakening it.

ARCHITECTURE.md section 13 tells Bob "never disable tests, never bypass safety checks".
A prompt is a request, not a control. The cheapest way for any agent to make a failing
suite pass is to delete the failing test, skip it, or assert nothing -- and a verification
step that then reports green would be measuring the guard rail, not the fix.

So the constraint is enforced on the *diff*, after the fact, whatever the agent claims:

    deleted-test-file      a test file removed outright
    net-test-removal       more `def test_*` lines removed than added across the patch
    disabled-test          skip / xfail / only markers added
    vacuous-assertion      `assert True` / `assert 1` added to a test file
    ci-config-touched      CI workflow files changed (bypassing the checks that gate merges)

A violation fails the remediation and rolls it back; it is not a warning. These are
heuristics over unified-diff text -- deliberately simple enough to explain in one line
each, and deliberately conservative (a false positive costs one retry; a false negative
costs a bogus "verified" outcome in the ledger).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_TEST_PATH = re.compile(r"(^|/)(tests?/|test_[^/]+$|[^/]+_test\.[a-z]+$)")
_TEST_DEF = re.compile(r"^\s*(?:async\s+)?def\s+test_\w+|^\s*it\(|^\s*test\(")
_DISABLED = re.compile(
    r"pytest\.mark\.(skip|skipif|xfail)|pytest\.skip\(|@unittest\.skip|\.only\(|\bxit\(|\bxdescribe\(|"
    r"pytest\.importorskip"
)
_VACUOUS = re.compile(r"^\s*assert\s+(True|1)\s*(#.*)?$")
_CI_FILE = re.compile(r"(^|/)(\.github/workflows/|\.gitlab-ci\.yml$|Jenkinsfile$|azure-pipelines\.yml$|\.circleci/)")


@dataclass(frozen=True)
class Violation:
    rule: str
    detail: str

    def __str__(self) -> str:
        return f"{self.rule}: {self.detail}"


def _files(diff: str) -> list[tuple[str, list[str], bool]]:
    """Split a unified diff into (path, body-lines, is_deletion)."""
    out: list[tuple[str, list[str], bool]] = []
    current: tuple[str, list[str], bool] | None = None
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            if current:
                out.append(current)
            m = re.match(r"diff --git a/(.+?) b/(.+)$", line)
            current = ((m.group(2) if m else line), [], False)
        elif current is not None:
            if line.startswith("deleted file mode"):
                current = (current[0], current[1], True)
            else:
                current[1].append(line)
    if current:
        out.append(current)
    return out


def check_patch(diff: str) -> list[Violation]:
    """Return every rule the diff breaks. Empty list means the patch may proceed."""
    violations: list[Violation] = []
    removed_tests = added_tests = 0

    for path, body, deleted in _files(diff):
        is_test = bool(_TEST_PATH.search(path))
        if _CI_FILE.search(path):
            violations.append(Violation("ci-config-touched", path))
        if deleted and is_test:
            violations.append(Violation("deleted-test-file", path))
        for line in body:
            if line.startswith("+++") or line.startswith("---"):
                continue
            text = line[1:]
            if line.startswith("-") and is_test and _TEST_DEF.match(text):
                removed_tests += 1
            elif line.startswith("+"):
                if is_test and _TEST_DEF.match(text):
                    added_tests += 1
                if is_test and _DISABLED.search(text):
                    violations.append(Violation("disabled-test", f"{path}: {text.strip()[:80]}"))
                if is_test and _VACUOUS.match(text):
                    violations.append(Violation("vacuous-assertion", f"{path}: {text.strip()}"))

    if removed_tests > added_tests:
        violations.append(Violation(
            "net-test-removal", f"{removed_tests} test definition(s) removed, {added_tests} added"))
    return violations
