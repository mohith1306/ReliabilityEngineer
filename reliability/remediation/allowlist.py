"""Which repositories BRE may write to. Deny by default.

Analysis is free; mutation is privileged (CLAUDE.md 4.5). An empty allowlist means BRE
can investigate anything it can read and change nothing -- which is the safe state for a
fresh checkout, a demo machine, or a CI runner.

    BRE_REPO_ALLOWLIST=/work/repos/payments-api;/work/repos/auth     (os.pathsep-separated)

An entry allows that directory and everything beneath it, so an entry should name a
specific repository, not a home directory. Entries are resolved (symlinks and `..`
collapsed) before comparison, so a path cannot be smuggled past the list.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Optional

ENV_ALLOWLIST = "BRE_REPO_ALLOWLIST"


class RepositoryNotAllowed(PermissionError):
    """The target repository is not on the write allowlist."""


class RepoAllowlist:
    def __init__(self, roots: Iterable[str | Path] = ()) -> None:
        self._roots = tuple(sorted({Path(r).expanduser().resolve() for r in roots if str(r).strip()}))

    @classmethod
    def from_env(cls, environ: Optional[dict] = None) -> "RepoAllowlist":
        raw = (environ if environ is not None else os.environ).get(ENV_ALLOWLIST, "")
        return cls(p for p in raw.split(os.pathsep) if p.strip())

    @property
    def roots(self) -> tuple[Path, ...]:
        return self._roots

    def allows(self, root: str | Path) -> bool:
        try:
            target = Path(root).expanduser().resolve()
        except OSError:
            return False
        return any(target == allowed or allowed in target.parents for allowed in self._roots)

    def assert_writable(self, root: str | Path) -> Path:
        if not self._roots:
            raise RepositoryNotAllowed(
                f"{ENV_ALLOWLIST} is empty: BRE is in read-only mode and will not modify {root}"
            )
        if not self.allows(root):
            raise RepositoryNotAllowed(
                f"{Path(root).resolve()} is not on the write allowlist "
                f"({', '.join(str(r) for r in self._roots)})"
            )
        return Path(root).resolve()
