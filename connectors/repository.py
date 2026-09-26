"""Repository structure: list files, detect project type, match keywords.

READ-ONLY. Never writes to the target repo (connectors/__init__.py invariant).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "venv", ".venv", "env",
    "__pycache__", ".pytest_cache", ".mypy_cache", "dist", "build",
    ".tox", ".eggs", "target", ".idea", ".vscode",
}
SKIP_SUFFIXES = {".pyc", ".pyo", ".so", ".dll", ".dylib", ".o", ".a", ".class"}

PROJECT_MARKERS = {
    "pyproject.toml": "python",
    "setup.py": "python",
    "requirements.txt": "python",
    "package.json": "node",
    "go.mod": "go",
    "Cargo.toml": "rust",
    "pom.xml": "java",
    "build.gradle": "java",
    "Gemfile": "ruby",
    "composer.json": "php",
}

MAX_FILE_BYTES = 256 * 1024
MAX_CONTENT_EVIDENCE = 20


@dataclass
class SourceFile:
    path: str
    size: int
    suffix: str


@dataclass
class RepoSnapshot:
    root: str
    project_type: str | None
    files: list[SourceFile] = field(default_factory=list)
    file_count: int = 0

    def paths(self) -> list[str]:
        return [f.path for f in self.files]


class RepositoryConnector:
    """Lists source files and detects the project type for a target repo."""

    def list_files(self, root: str) -> list[SourceFile]:
        root_path = Path(root).resolve()
        if not root_path.is_dir():
            raise FileNotFoundError(f"Repository root does not exist: {root}")

        results: list[SourceFile] = []
        for dirpath, dirnames, filenames in os.walk(root_path):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                if Path(name).suffix in SKIP_SUFFIXES:
                    continue
                full = Path(dirpath) / name
                try:
                    stat = full.stat()
                except OSError:
                    continue
                # POSIX separators on every OS: paths are evidence refs, compared and
                # stored as strings, and must not depend on who ran the investigation.
                rel = full.relative_to(root_path).as_posix()
                results.append(SourceFile(path=rel, size=stat.st_size, suffix=full.suffix))
        results.sort(key=lambda f: f.path)
        return results

    def detect_project_type(self, root: str) -> str | None:
        root_path = Path(root)
        for marker, ptype in PROJECT_MARKERS.items():
            if (root_path / marker).exists():
                return ptype
        return None

    def snapshot(self, root: str) -> RepoSnapshot:
        files = self.list_files(root)
        return RepoSnapshot(
            root=str(Path(root).resolve()),
            project_type=self.detect_project_type(root),
            files=files,
            file_count=len(files),
        )

    def find_files_matching(
        self, root: str, keywords: list[str], *, max_results: int = 10
    ) -> list[tuple[str, float]]:
        """Return (path, score) for files whose path or name matches keywords.

        Score is the fraction of distinct keywords hit, in [0, 1].
        """
        if not keywords:
            return []
        lowered = [k.lower() for k in keywords]
        hits: list[tuple[str, float]] = []
        for sf in self.list_files(root):
            haystack = sf.path.lower().replace("\\", "/")
            name = os.path.basename(haystack)
            distinct = sum(1 for k in lowered if k in haystack or k in name)
            if distinct:
                hits.append((sf.path, distinct / len(lowered)))
        hits.sort(key=lambda t: (-t[1], t[0]))
        return hits[:max_results]

    def read_file(self, root: str, rel_path: str, *, max_bytes: int = MAX_FILE_BYTES) -> str:
        """Read a file under root. Refuses paths that escape root (traversal guard)."""
        root_path = Path(root).resolve()
        target = (root_path / rel_path).resolve()
        if not str(target).startswith(str(root_path) + os.sep) and target != root_path:
            raise ValueError(f"Path escapes repository root: {rel_path}")
        data = target.read_bytes()[:max_bytes]
        return data.decode("utf-8", errors="replace")

    def files_mentioning(
        self, root: str, pattern: str, *, max_results: int = 10
    ) -> list[tuple[str, float]]:
        """Return (path, score) for source files whose content matches a regex pattern."""
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            return []
        results: list[tuple[str, float]] = []
        for sf in self.list_files(root):
            if sf.suffix not in {".py", ".js", ".ts", ".go", ".java", ".rb", ".rs", ".md", ".yaml", ".yml", ".toml", ".cfg", ".ini"}:
                continue
            if sf.size > MAX_FILE_BYTES:
                continue
            try:
                text = self.read_file(root, sf.path, max_bytes=MAX_FILE_BYTES)
            except (OSError, ValueError):
                continue
            matches = regex.findall(text)
            if matches:
                score = min(1.0, len(matches) / 5)
                results.append((sf.path, score))
        results.sort(key=lambda t: (-t[1], t[0]))
        return results[:max_results]
