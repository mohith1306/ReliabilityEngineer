"""S6 -- the write path. Every test here is about something that must NOT happen.

Exit criteria (docs/stages/STAGES.md):
  * a git checkpoint is created before any patch is applied
  * changes land on a branch, never on the target's default branch
  * changed files are recorded against the remediation record (from git)
  * the repository allowlist is enforced; a write to a non-allowlisted repo is rejected

Plus the properties that make those meaningful: failure rolls back exactly, a lying
executor cannot falsify the record, an agent cannot turn the suite green by deleting the
failing test, and rollback never touches the user's own untracked files.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from apps.api.database import ApprovalDB, IncidentDB, OutcomeRecordDB, RemediationDB, RiskAssessmentDB, generate_id
from models.outcome import PredictionType
from reliability.orchestration.gate import GateViolation
from reliability.remediation import git_ops, guards
from reliability.remediation.allowlist import RepoAllowlist, RepositoryNotAllowed
from reliability.remediation.engine import RemediationEngine, RemediationRefused
from reliability.remediation.executors import ExecutorResult, ReplayExecutor, select_executor
from reliability.remediation.git_ops import DirtyWorktree

REPO_ROOT = Path(__file__).resolve().parents[2]
DIAGNOSIS = {"root_cause": "pool_size lowered to 2", "confidence": 0.86,
             "affected_components": ["config/app.yaml"]}


@pytest.fixture(autouse=True)
def _replay(monkeypatch):
    monkeypatch.setenv("BRE_BOB_TRANSPORT", "replay")


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def make_incident(db, *, status="REMEDIATING", risk="LOW") -> IncidentDB:
    row = IncidentDB(id=generate_id(), repository="seeded_failure", type="test_failure", severity="high",
                     status=status, description="pool exhaustion", metadata_json={})
    db.add(row)
    if risk:
        db.add(RiskAssessmentDB(id=generate_id(), incident_id=row.id, risk_level=risk, factors={}))
    db.flush()
    return row


class Fake:
    """An executor that does whatever the test scripts, and can lie about it."""

    def __init__(self, act, *, summary="fake summary", name="fake"):
        self.name, self._act, self._summary = name, act, summary

    def apply(self, prompt, *, repo_root):
        self._act(Path(repo_root))
        return ExecutorResult(summary=self._summary, tokens=10, wall_ms=1.0, provider="fake")


def engine(db, repo, executor=None, allow=True):
    return RemediationEngine(
        db, executor=executor or ReplayExecutor(),
        allowlist=RepoAllowlist([repo.parent] if allow else []),
    )


def run(db, repo, executor=None, **kw):
    inc = make_incident(db)
    result = engine(db, repo, executor, **kw).run(inc, repo_root=str(repo), diagnosis=DIAGNOSIS)
    return inc, result


def tree_state(repo):
    return (git_ops.current_branch(repo), git_ops.head_sha(repo), git(repo, "status", "--porcelain"))


# ── the happy path, and what it proves ────────────────────────────────────────


def test_checkpoint_then_branch_never_the_default_branch(db, seeded_repo):
    base_branch, base_sha, _ = tree_state(seeded_repo)
    inc, result = run(db, seeded_repo)

    assert result.ok, result.reason
    row = result.remediation
    assert row.checkpoint_sha == base_sha  # recorded BEFORE the patch
    assert row.base_branch == base_branch
    assert row.patch_reference.startswith("bre/") and row.patch_reference != base_branch
    assert git_ops.current_branch(seeded_repo) == row.patch_reference
    assert git(seeded_repo, "rev-parse", base_branch) == base_sha, "the default branch must not move"
    assert git(seeded_repo, "rev-parse", f"refs/bre/checkpoints/{inc.id}-attempt-1") == base_sha
    assert git(seeded_repo, "rev-parse", "HEAD") != base_sha  # a patch commit exists on the bre branch


def test_changed_files_are_recorded_from_git(db, seeded_repo):
    _, result = run(db, seeded_repo)
    assert result.remediation.changed_files == ["config/app.yaml"]
    assert result.remediation.status == "completed"
    assert result.remediation.commit_sha


def test_a_lying_executor_cannot_falsify_the_changed_files(db, seeded_repo):
    def act(root):  # edits config but the summary below claims README.md
        text = (root / "config/app.yaml").read_bytes().decode()
        (root / "config/app.yaml").write_bytes(text.replace("pool_size: 2", "pool_size: 20").encode())

    _, result = run(db, seeded_repo, Fake(act, summary="I only touched README.md, honest"))
    assert result.remediation.changed_files == ["config/app.yaml"]


def test_baseline_is_measured_before_the_patch(db, seeded_repo):
    _, result = run(db, seeded_repo)
    assert result.remediation.baseline_failures == ["tests/test_dbpool.py::test_pool_sized_from_config"]


def test_remediation_opens_a_pending_prediction_with_cost_and_simulated_flag(db, seeded_repo):
    inc, result = run(db, seeded_repo)
    [rec] = db.query(OutcomeRecordDB).filter_by(incident_id=inc.id).all()
    assert rec.prediction_type == PredictionType.REMEDIATION_PLAN.value
    assert rec.status == "pending"  # only verification may close it
    assert rec.cost_tokens == 6100
    assert rec.components["simulated"] is True and rec.components["executor"] == "replay"


def test_the_run_leaves_no_test_litter_in_the_target(db, seeded_repo):
    run(db, seeded_repo)
    assert git(seeded_repo, "status", "--porcelain", "--untracked-files=all") == ""


# ── allowlist: deny by default ───────────────────────────────────────────────


def test_empty_allowlist_is_read_only_mode(db, seeded_repo):
    before = tree_state(seeded_repo)
    inc = make_incident(db)
    with pytest.raises(RepositoryNotAllowed, match="read-only"):
        engine(db, seeded_repo, allow=False).run(inc, repo_root=str(seeded_repo), diagnosis=DIAGNOSIS)
    assert tree_state(seeded_repo) == before


def test_a_repo_outside_the_allowlist_is_rejected_and_untouched(db, seeded_repo, tmp_path_factory):
    elsewhere = tmp_path_factory.mktemp("elsewhere")
    before = tree_state(seeded_repo)
    inc = make_incident(db)
    eng = RemediationEngine(db, executor=ReplayExecutor(), allowlist=RepoAllowlist([elsewhere]))
    with pytest.raises(RepositoryNotAllowed, match="not on the write allowlist"):
        eng.run(inc, repo_root=str(seeded_repo), diagnosis=DIAGNOSIS)
    assert tree_state(seeded_repo) == before
    assert not db.query(RemediationDB).all()


def test_allowlist_cannot_be_escaped_with_dotdot(tmp_path):
    allowed = tmp_path / "safe"
    (allowed).mkdir()
    (tmp_path / "secret").mkdir()
    lst = RepoAllowlist([allowed])
    assert lst.allows(allowed)
    assert not lst.allows(allowed / ".." / "secret")


# ── the gate and the state, re-checked inside the engine ─────────────────────


def test_engine_refuses_outside_remediating(db, seeded_repo):
    inc = make_incident(db, status="RISK_ASSESSED")
    with pytest.raises(RemediationRefused, match="REMEDIATING"):
        engine(db, seeded_repo).run(inc, repo_root=str(seeded_repo), diagnosis=DIAGNOSIS)


def test_engine_rechecks_the_gate_even_if_the_status_was_forced(db, seeded_repo):
    """The DB row says REMEDIATING, but there is a HIGH risk and no approval: someone edited
    the row by hand. The engine must not trust the status column."""
    before = tree_state(seeded_repo)
    inc = make_incident(db, status="REMEDIATING", risk="HIGH")
    with pytest.raises(GateViolation):
        engine(db, seeded_repo).run(inc, repo_root=str(seeded_repo), diagnosis=DIAGNOSIS)
    assert tree_state(seeded_repo) == before


# ── a dirty tree is refused, never mixed ─────────────────────────────────────


def test_uncommitted_tracked_changes_are_refused_and_preserved(db, seeded_repo):
    (seeded_repo / "dbpool.py").write_text("# somebody's unsaved work\n", encoding="utf-8")
    with pytest.raises(DirtyWorktree):
        run(db, seeded_repo)
    assert (seeded_repo / "dbpool.py").read_text(encoding="utf-8") == "# somebody's unsaved work\n"
    assert git_ops.current_branch(seeded_repo) != "bre"  # never switched away


# ── every failure path rolls back exactly ────────────────────────────────────


def assert_restored(repo, base_branch, base_sha):
    assert git_ops.current_branch(repo) == base_branch
    assert git_ops.head_sha(repo) == base_sha
    assert git(repo, "branch", "--list", "bre/*") == ""
    assert git_ops.tracked_modifications(repo) == []


def test_executor_crash_rolls_back_to_the_checkpoint(db, seeded_repo):
    base_branch, base_sha, _ = tree_state(seeded_repo)

    def act(root):
        (root / "config/app.yaml").write_text("garbage\n", encoding="utf-8")
        raise RuntimeError("bob exploded mid-edit")

    _, result = run(db, seeded_repo, Fake(act))
    assert not result.ok and "bob exploded" in result.reason
    assert_restored(seeded_repo, base_branch, base_sha)
    assert result.remediation.status == "failed" and result.remediation.rolled_back_at


def test_no_op_executor_is_a_failure_not_a_success(db, seeded_repo):
    base_branch, base_sha, _ = tree_state(seeded_repo)
    _, result = run(db, seeded_repo, Fake(lambda root: None))
    assert not result.ok and "changed no files" in result.reason
    assert_restored(seeded_repo, base_branch, base_sha)


def test_rollback_never_deletes_the_users_own_untracked_files(db, seeded_repo):
    (seeded_repo / "notes.txt").write_text("my scratch notes\n", encoding="utf-8")  # untracked, pre-existing
    base_branch, base_sha, _ = tree_state(seeded_repo)

    def act(root):
        (root / "new_module.py").write_text("x = 1\n", encoding="utf-8")  # the agent's own file
        raise RuntimeError("fail after creating a file")

    _, result = run(db, seeded_repo, Fake(act))
    assert not result.ok
    assert (seeded_repo / "notes.txt").read_text(encoding="utf-8") == "my scratch notes\n"
    assert not (seeded_repo / "new_module.py").exists()
    assert_restored(seeded_repo, base_branch, base_sha)


# ── the agent cannot make the suite green by weakening it ────────────────────


def test_deleting_the_failing_test_is_caught_rolled_back_and_kept_as_evidence(db, seeded_repo):
    base_branch, base_sha, _ = tree_state(seeded_repo)

    def act(root):
        (root / "tests" / "test_dbpool.py").unlink()

    inc, result = run(db, seeded_repo, Fake(act))
    assert not result.ok
    assert any(v.rule == "deleted-test-file" for v in result.guard_violations)
    assert_restored(seeded_repo, base_branch, base_sha)
    # the rejected patch stays inspectable
    assert git(seeded_repo, "rev-parse", "--verify", f"refs/bre/failed/{inc.id}-attempt-1")


def test_skipping_the_failing_test_is_caught(db, seeded_repo):
    def act(root):
        p = root / "tests" / "test_dbpool.py"
        p.write_bytes(p.read_bytes().decode().replace(
            "def test_pool_sized_from_config", "@pytest.mark.skip\ndef test_pool_sized_from_config").encode())

    _, result = run(db, seeded_repo, Fake(act))
    assert not result.ok and any(v.rule == "disabled-test" for v in result.guard_violations)


@pytest.mark.parametrize("diff,rule", [
    ("diff --git a/tests/test_x.py b/tests/test_x.py\ndeleted file mode 100644\n--- a/tests/test_x.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-def test_a(): pass\n", "deleted-test-file"),
    ("diff --git a/tests/test_x.py b/tests/test_x.py\n--- a/tests/test_x.py\n+++ b/tests/test_x.py\n@@ -1,2 +1 @@\n-def test_a(): pass\n-def test_b(): pass\n+def test_a(): pass\n", "net-test-removal"),
    ("diff --git a/tests/test_x.py b/tests/test_x.py\n--- a/tests/test_x.py\n+++ b/tests/test_x.py\n@@ -1 +1,2 @@\n+@pytest.mark.xfail\n def test_a(): pass\n", "disabled-test"),
    ("diff --git a/tests/test_x.py b/tests/test_x.py\n--- a/tests/test_x.py\n+++ b/tests/test_x.py\n@@ -1 +1 @@\n-    assert compute() == 3\n+    assert True\n", "vacuous-assertion"),
    ("diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml\n--- a/.github/workflows/ci.yml\n+++ b/.github/workflows/ci.yml\n@@ -1 +1 @@\n-run: pytest\n+run: echo ok\n", "ci-config-touched"),
])
def test_each_guard_rule_fires(diff, rule):
    assert rule in {v.rule for v in guards.check_patch(diff)}


def test_a_legitimate_config_fix_passes_the_guard():
    diff = ("diff --git a/config/app.yaml b/config/app.yaml\n--- a/config/app.yaml\n"
            "+++ b/config/app.yaml\n@@ -1 +1 @@\n-  pool_size: 2\n+  pool_size: 20\n")
    assert guards.check_patch(diff) == []


def test_adding_a_test_alongside_a_fix_is_allowed():
    diff = ("diff --git a/tests/test_new.py b/tests/test_new.py\nnew file mode 100644\n"
            "--- /dev/null\n+++ b/tests/test_new.py\n@@ -0,0 +1,2 @@\n+def test_pool_size_default():\n+    assert 20 == 20\n")
    assert guards.check_patch(diff) == []


# ── the write path stays grep-able ───────────────────────────────────────────


def test_exactly_one_allow_writes_true_exists_outside_tests():
    """AST, not grep: docstrings and messages legitimately mention the flag."""
    import ast

    hits = []
    for path in REPO_ROOT.rglob("*.py"):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel.startswith(("tests/", "venv/", ".venv/", "scripts/")):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if kw.arg == "allow_writes" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        hits.append(f"{rel}:{node.lineno}")
    assert len(hits) == 1 and hits[0].startswith("reliability/remediation/executors.py"), hits


def test_replay_is_never_selected_silently(monkeypatch):
    monkeypatch.delenv("BRE_BOB_TRANSPORT", raising=False)
    monkeypatch.delenv("BOB_API_KEY", raising=False)
    from bob.errors import BobNotAvailable
    with pytest.raises(BobNotAvailable, match="BRE_BOB_TRANSPORT=replay"):
        select_executor()
