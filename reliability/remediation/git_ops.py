"""Git operations for the write path: checkpoint, branch, commit, rollback.

These are the *only* functions in the codebase that mutate a target repository's git
state, and the remediation engine is the only caller. The safety properties they carry:

  CHECKPOINT  Before any patch, the repo's HEAD is recorded (`base_sha`) and pinned under
              `refs/bre/checkpoints/<name>`, so rollback survives even if the patch branch
              is deleted. A repo with modified tracked files is REFUSED: BRE will not mix
              its patch with someone's uncommitted work, and could not roll back cleanly.
  BRANCH-ONLY Work happens on a fresh `bre/<incident>/attempt-<n>` branch. `assert_on_bre_
              branch` is called before every write-shaped operation; the default branch is
              never checked out for writing.
  ROLLBACK    Returns the repo to `base_branch` and removes ONLY what the remediation
              created (files untracked at checkpoint time are left alone). The failed patch
              stays reachable under `refs/bre/failed/...` -- a rolled-back attempt is
              evidence for the next attempt, not something to erase.
  CHANGED     `changed_files` come from git, never from what an agent says it changed
              (Bob's JSON has no such field; git records what actually happened).
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

BRANCH_PREFIX = "bre/"
BRE_IDENTITY = ["-c", "user.name=BRE Remediation", "-c", "user.email=bre@localhost",
                "-c", "commit.gpgsign=false"]

# Never staged, never counted as a change: interpreter/test-runner litter.
_JUNK = re.compile(r"(^|/)(__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache|node_modules)(/|$)|\.py[co]$")


class GitError(RuntimeError):
    """A git command failed, or a safety precondition did not hold."""


class DirtyWorktree(GitError):
    """Tracked files have uncommitted modifications; refusing to write."""


class NotOnBreBranch(GitError):
    """A write-shaped operation was attempted off a bre/* branch."""


def _git(root: str | Path, *args: str, check: bool = True, identity: bool = False) -> str:
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C")
    cmd = ["git", *(BRE_IDENTITY if identity else []), *args]
    proc = subprocess.run(
        cmd, cwd=str(root), capture_output=True, text=True, env=env,
        encoding="utf-8", errors="replace",
    )
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()[:400]}")
    return proc.stdout.strip()


def slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-")[:60] or "x"


@dataclass(frozen=True)
class Checkpoint:
    root: str
    base_branch: str
    base_sha: str
    branch: str
    ref: str
    preexisting_untracked: frozenset[str] = field(default_factory=frozenset)


def is_git_repo(root: str | Path) -> bool:
    return _git(root, "rev-parse", "--is-inside-work-tree", check=False) == "true"


def head_sha(root: str | Path) -> str:
    return _git(root, "rev-parse", "HEAD")


def current_branch(root: str | Path) -> str:
    return _git(root, "rev-parse", "--abbrev-ref", "HEAD")


def _paths(root: str | Path, *args: str) -> list[str]:
    """NUL-separated path list. Never parse `git status --porcelain`: its first column is a
    significant space, and any `.strip()` upstream silently eats the first character of the
    first path (this shipped as `onfig/app.yaml` before a test caught it)."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C")
    proc = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args], cwd=str(root),
        capture_output=True, env=env,
    )
    if proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {proc.stderr.decode('utf-8', 'replace')[:300]}")
    return [p.decode("utf-8", "replace") for p in proc.stdout.split(b"\0") if p]


def tracked_modifications(root: str | Path) -> list[str]:
    """TRACKED files that differ from HEAD (staged or not, including deletions).
    Untracked files are deliberately excluded."""
    return _paths(root, "diff", "--name-only", "-z", "HEAD")


def untracked_files(root: str | Path) -> set[str]:
    return {p for p in _paths(root, "ls-files", "--others", "--exclude-standard", "-z")
            if not _JUNK.search(p)}


def assert_on_bre_branch(root: str | Path) -> str:
    branch = current_branch(root)
    if not branch.startswith(BRANCH_PREFIX):
        raise NotOnBreBranch(
            f"refusing to write: HEAD is {branch!r}, not a {BRANCH_PREFIX}* branch. "
            "Remediation never touches the target's own branches."
        )
    return branch


def create_checkpoint(root: str | Path, incident_id: str, attempt: int) -> Checkpoint:
    """Pin HEAD, then switch to a fresh working branch. Raises before changing anything."""
    root = str(root)
    if not is_git_repo(root):
        raise GitError(f"{root} is not a git repository; cannot checkpoint")
    dirty = tracked_modifications(root)
    if dirty:
        raise DirtyWorktree(
            f"{len(dirty)} tracked file(s) have uncommitted changes ({', '.join(dirty[:3])}...); "
            "commit or stash them first -- BRE will not mix a patch with unsaved work"
        )
    base_branch = current_branch(root)
    if base_branch.startswith(BRANCH_PREFIX):
        raise GitError(f"already on {base_branch}; a previous remediation was not cleaned up")
    base_sha = head_sha(root)

    name = f"{slug(incident_id)}-attempt-{attempt}"
    branch = f"{BRANCH_PREFIX}{slug(incident_id)}/attempt-{attempt}"
    ref = f"refs/bre/checkpoints/{name}"
    preexisting = frozenset(untracked_files(root))

    if _git(root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", check=False):
        raise GitError(f"branch {branch} already exists")
    _git(root, "update-ref", ref, base_sha)
    _git(root, "switch", "-c", branch)
    return Checkpoint(root, base_branch, base_sha, branch, ref, preexisting)


def working_changes(cp: Checkpoint) -> list[str]:
    """Everything the remediation changed so far: tracked edits plus files it created."""
    assert_on_bre_branch(cp.root)
    tracked = set(tracked_modifications(cp.root))
    created = untracked_files(cp.root) - set(cp.preexisting_untracked)
    return sorted(p for p in (tracked | created) if not _JUNK.search(p))


def commit_changes(cp: Checkpoint, message: str) -> Optional[str]:
    """Commit the remediation's changes on the bre/* branch. None if there is nothing."""
    assert_on_bre_branch(cp.root)
    changes = working_changes(cp)
    if not changes:
        return None
    _git(cp.root, "add", "-A", "--", *changes)
    _git(cp.root, "commit", "-q", "-m", message, identity=True)
    return head_sha(cp.root)


def changed_files(cp: Checkpoint) -> list[str]:
    """Files that differ between the checkpoint and the patch commit -- from git."""
    out = _git(cp.root, "diff", "--name-only", cp.base_sha, "HEAD")
    return sorted(p for p in out.splitlines() if p and not _JUNK.search(p))


def patch_diff(cp: Checkpoint) -> str:
    return _git(cp.root, "diff", "--no-color", cp.base_sha, "HEAD")


def diff_between(root: str | Path, base_sha: str, commit_sha: str) -> str:
    """The stored patch, re-derivable later from two shas (used by the dashboard)."""
    return _git(root, "diff", "--no-color", base_sha, commit_sha)


def added_files(cp: Checkpoint) -> list[str]:
    """Files the patch created (as opposed to modified)."""
    out = _git(cp.root, "diff", "--name-only", "--diff-filter=A", cp.base_sha, "HEAD")
    return sorted(p for p in out.splitlines() if p and not _JUNK.search(p))


def rollback(cp: Checkpoint, *, keep_as: Optional[str] = None) -> None:
    """Return to the base branch, discarding only what this remediation made.

    `keep_as` names a ref under refs/bre/failed/ that keeps the abandoned patch reachable.
    """
    root = cp.root
    on = current_branch(root)
    if on == cp.branch:
        # Files this remediation created and never committed.
        for path in untracked_files(root) - set(cp.preexisting_untracked):
            target = Path(root) / path
            try:
                target.unlink()
            except OSError:
                pass
        _git(root, "reset", "--hard", "-q", "HEAD")  # discard tracked edits on the bre branch only
        if keep_as:
            _git(root, "update-ref", f"refs/bre/failed/{keep_as}", head_sha(root))
        _git(root, "switch", "-q", cp.base_branch)
    _git(root, "branch", "-D", cp.branch, check=False)
    if current_branch(root) != cp.base_branch:
        raise GitError(f"rollback left HEAD on {current_branch(root)!r}, expected {cp.base_branch!r}")
    if head_sha(root) != cp.base_sha:
        raise GitError(
            f"rollback left {cp.base_branch} at {head_sha(root)[:8]}, expected checkpoint {cp.base_sha[:8]}"
        )


def files_touching_tests(paths: Iterable[str]) -> list[str]:
    return [p for p in paths if re.search(r"(^|/)(tests?/|test_[^/]+$|[^/]+_test\.[a-z]+$)", p)]
