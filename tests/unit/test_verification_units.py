"""Verification building blocks: report parsing, and the refusal to call an empty run a pass."""

from __future__ import annotations

from reliability.verification.test_runner import CaseResult, RunResult, Scope, TestRunner, parse_pytest_report
from reliability.verification.verifier import extract_test_ids

REPORT = """\
============================= test session starts =============================
tests/test_dbpool.py .F                                                  [100%]
=========================== short test summary info ============================
PASSED tests/test_dbpool.py::test_release_returns_slot
FAILED tests/test_dbpool.py::test_pool_sized_from_config - AssertionError: assert 2 >= 10
SKIPPED [1] tests/test_x.py:12: not on windows
ERROR tests/test_broken.py::test_needs_fixture - fixture 'db' not found
PASSED tests/test_dbpool.py::test_release_returns_slot
"""


def test_report_parsing_extracts_each_outcome_once():
    cases = {(c.name, c.outcome) for c in parse_pytest_report(REPORT)}
    assert ("tests/test_dbpool.py::test_release_returns_slot", "passed") in cases
    assert ("tests/test_dbpool.py::test_pool_sized_from_config", "failed") in cases
    assert ("tests/test_broken.py::test_needs_fixture", "error") in cases
    assert ("tests/test_x.py", "skipped") in cases
    assert len([c for c in parse_pytest_report(REPORT) if c.outcome == "passed"]) == 1  # de-duplicated


def test_failure_message_is_kept():
    failed = [c for c in parse_pytest_report(REPORT) if c.outcome == "failed"][0]
    assert "assert 2 >= 10" in failed.message


def _run(rc, cases):
    return RunResult(Scope.REGRESSION, ["pytest"], rc, [CaseResult(n, o) for n, o in cases])


def test_a_run_that_ran_nothing_is_not_a_pass():
    assert not _run(0, []).ok  # exit 0 but zero tests: a green light that proves nothing
    assert not _run(5, []).ok  # pytest's "no tests collected"


def test_only_a_clean_nonempty_run_is_ok():
    assert _run(0, [("a", "passed")]).ok
    assert not _run(1, [("a", "passed"), ("b", "failed")]).ok
    assert not _run(0, [("a", "passed"), ("b", "error")]).ok  # an error is not a pass even if rc lies


def test_a_timeout_is_never_ok():
    r = _run(0, [("a", "passed")])
    r.timed_out = True
    assert not r.ok


def test_runner_on_a_directory_with_no_tests_reports_not_ok(tmp_path):
    result = TestRunner(timeout_s=60).run(tmp_path, Scope.REGRESSION)
    assert not result.ok and result.ran == 0


def test_runner_reports_pass_and_fail_and_leaves_no_litter(tmp_path):
    (tmp_path / "test_a.py").write_text("def test_ok():\n    assert True\n\ndef test_bad():\n    assert 1 == 2\n")
    result = TestRunner(timeout_s=60).run(tmp_path, Scope.REGRESSION)
    assert not result.ok
    assert "test_a.py::test_ok" in result.passed
    assert result.failing == {"test_a.py::test_bad"}
    leftovers = {p.name for p in tmp_path.rglob("*")} - {"test_a.py"}
    assert leftovers == set(), f"the runner wrote into the target: {leftovers}"  # no .pytest_cache, no __pycache__


def test_node_ids_are_extracted_and_forward_slashed():
    text = r"FAILED tests\test_dbpool.py::test_pool_sized_from_config and ci/failure.log::tests/test_x.py::test_y"
    assert extract_test_ids(text) == ["tests/test_dbpool.py::test_pool_sized_from_config", "tests/test_x.py::test_y"]
    assert extract_test_ids(None, "", {"a": 1}) == []
