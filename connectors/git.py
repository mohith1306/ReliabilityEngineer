"""Git history: recent commits, blame, diffs. READ-ONLY.

Uses GitPython (already a declared dependency). Every method is read-only;
no branch is created, no ref is moved, nothing is committed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

try:
    import git
except ImportError:  # pragma: no cover - gitpython is in requirements.txt
    git = None


@dataclass
class GitCommitInfo:
    sha: str
    short_sha: str
    author: str
    authored_at: str
    message: str
    files_changed: list[str] = field(default_factory=list)


@dataclass
class GitFileHistory:
    path: str
    commits: list[GitCommitInfo] = field(default_factory=list)


@dataclass
class GitDiffInfo:
    path: str
    commit_sha: str
    diff: str


class GitConnector:
    """Commit history, blame and diffs for a target repository. Read-only."""

    def __init__(self) -> None:
        if git is None:
            raise RuntimeError("gitpython is not installed")

    def _repo(self, root: str):
        root_path = Path(root).resolve()
        if not root_path.is_dir():
            raise FileNotFoundError(f"Repository root does not exist: {root}")
        try:
            return git.Repo(str(root_path), search_parent_directories=False)
        except git.exc.NoSuchPathError as exc:
            raise FileNotFoundError(f"Not a git repository: {root}") from exc
        except git.exc.InvalidGitRepositoryError as exc:
            raise ValueError(f"Not a git repository: {root}") from exc

    @staticmethod
    def _to_info(commit) -> GitCommitInfo:
        files = list(commit.stats.files)  # stats.files is a {path: counts} dict
        return GitCommitInfo(
            sha=commit.hexsha,
            short_sha=commit.hexsha[:7],
            author=str(commit.author),
            authored_at=commit.authored_datetime.isoformat(),
            message=str(commit.message).strip(),
            files_changed=files,
        )

    def recent_commits(self, root: str, *, limit: int = 10) -> list[GitCommitInfo]:
        repo = self._repo(root)
        commits = list(repo.iter_commits(max_count=limit))
        return [self._to_info(c) for c in commits]

    def log_for_paths(self, root: str, paths: list[str], *, limit: int = 5) -> list[GitCommitInfo]:
        """Commits touching any of the given paths, newest first."""
        if not paths:
            return []
        repo = self._repo(root)
        commits = list(repo.iter_commits(paths=paths, max_count=limit))
        return [self._to_info(c) for c in commits]

    def blame(self, root: str, rel_path: str) -> list[dict]:
        """Line-level blame for one file: [{line, sha, author}, ...]."""
        repo = self._repo(root)
        rows: list[dict] = []
        lineno = 0
        # Repo.blame yields (commit, [line_text, ...]) groups, not per-line pairs.
        for commit, lines in repo.blame("HEAD", rel_path):
            for _text in lines:
                lineno += 1
                rows.append({
                    "line": lineno,
                    "sha": commit.hexsha[:7],
                    "author": str(commit.author),
                })
        return rows

    def diff_for_commit(self, root: str, sha: str) -> list[GitDiffInfo]:
        repo = self._repo(root)
        commit = repo.commit(sha)
        diffs: list[GitDiffInfo] = []
        if commit.parents:
            parent = commit.parents[0]
            diff_index = parent.diff(commit, create_patch=True)
        else:
            diff_index = commit.diff(git.NULL_TREE, create_patch=True)
        for d in diff_index:
            path = d.a_path or d.b_path
            raw = d.diff
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")
            diffs.append(GitDiffInfo(path=path, commit_sha=sha, diff=raw))
        return diffs

    def working_tree_dirty(self, root: str) -> bool:
        repo = self._repo(root)
        return bool(repo.is_dirty())
