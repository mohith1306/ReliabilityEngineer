"""Git connector -- commit history into claim events. Stage S2.

Read-only. Shells out to git rather than taking a gitpython dependency: the four
plumbing calls needed here are stable, and subprocess keeps the connector usable
against a bare checkout with no library assumptions.

Claim-event semantics follow ASMOS's git_ownership prototype:

    merged to the mainline  -> a VERIFIED claim by its author, on the topics its
                               files touch
    a detected git revert   -> a REFUTED claim, credited back to the ORIGINAL
                               author, recorded as a new event rather than a
                               mutation of the original (corrections supersede)

Identity resolution is BRE's own addition and it is not cosmetic -- see
`resolve_identities`. The upstream prototype keys agents on the raw author name,
which on a real repository splits one person across many agent ids and thereby
understates ownership concentration.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional

_REVERT_SUBJECT_RE = re.compile(r'^Revert\s+"', re.IGNORECASE)
_REVERTS_COMMIT_RE = re.compile(r"This reverts commit ([0-9a-f]{7,40})", re.IGNORECASE)

# Record / unit separators: will not collide with commit message text.
_RS, _US = "\x1e", "\x1f"

# Directories that are never a subsystem topic.
_NON_TOPIC = {
    ".git", ".github", ".claude", "node_modules", "venv", ".venv", "__pycache__",
    "dist", "build", "site-packages", ".pytest_cache", ".ruff_cache", ".mypy_cache",
}


@dataclass(frozen=True)
class Commit:
    sha: str
    author_name: str
    author_email: str
    timestamp: str
    subject: str
    body: str
    files: tuple[str, ...] = ()


@dataclass(frozen=True)
class ClaimEvent:
    """One verified or refuted claim, shaped for asmos.e6.asymmetry.

    That module reads only topic / agent_id / is_accepted / score. The rest is
    carried through for the ownership replay and for evidence.
    """

    topic: str
    agent_id: str
    is_accepted: bool
    score: int
    sha: str
    timestamp: str
    subject: str
    kind: str  # "commit" | "revert"

    def as_dict(self) -> dict:
        return {
            "topic": self.topic,
            "agent_id": self.agent_id,
            "is_accepted": self.is_accepted,
            "score": self.score,
            "sha": self.sha,
            "timestamp": self.timestamp,
            "subject": self.subject,
            "kind": self.kind,
        }


def resolve_identities(pairs: Iterable[tuple[str, str]]) -> dict[tuple[str, str], str]:
    """Collapse (name, email) pairs into one stable agent id per human.

    Neither name nor email alone identifies a person. Observed in a real
    repository (session 0004): one contributor appears under two names sharing an
    email, and another under one name spread across eight emails because git
    defaulted to `user@hostname` on six different machines.

    Treat it as connected components over a bipartite name/email graph: two pairs
    belong to the same person if they share a name OR an email, transitively. The
    component's most frequent email wins as the id, because an email is more
    stable than a display name.

    This matters for the measurement, not just for tidiness. Splitting one person
    across N agent ids spreads their contributions across N rows, which lowers the
    per-topic top-agent share and so **understates** ownership concentration. An
    unnormalized OCI is biased toward "no asymmetry here."
    """
    pairs = [(n.strip(), _normalize_email(e)) for n, e in pairs]
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for name, email in pairs:
        # Namespaced so a name can never collide with an email.
        union(f"n:{_normalize_name(name)}", f"e:{email}")

    # Pick a display id per component: the most common email in it.
    email_counts: dict[str, dict[str, int]] = {}
    for name, email in pairs:
        root = find(f"e:{email}")
        email_counts.setdefault(root, {})
        email_counts[root][email] = email_counts[root].get(email, 0) + 1

    resolved: dict[tuple[str, str], str] = {}
    for name, email in pairs:
        root = find(f"e:{email}")
        counts = email_counts.get(root, {email: 1})
        resolved[(name, email)] = max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0]
    return resolved


_QUOTES = "\"'“”‘’"


def _normalize_name(name: str) -> str:
    """Fold display-name noise: case, spacing, and stray smart quotes."""
    cleaned = name.strip().strip(_QUOTES).replace(" ", "").lower()
    return cleaned or "unknown"


def _normalize_email(email: str) -> str:
    """Fold email noise.

    Observed in real history: a contributor whose git config carried a smart quote
    inside the email itself, producing an address that differs from their real one
    by a single invisible character and so resolves to a separate person.
    """
    return email.strip().strip(_QUOTES).lower() or "unknown"


def default_topic_fn(repo_root: Path, *, source_dirs: Optional[set[str]] = None) -> Callable:
    """Map a changed path to the topic(s) it touches.

    Topics are the repository's own subsystem boundaries. The upstream prototype
    hardcoded one project's directory names; BRE derives them, because it must run
    against repositories it has never seen.

    Rule: the first path segment, or the second when the first is a recognised
    source root (src/, lib/, apps/, pkg/). Files with no meaningful segment -- root
    config, loose scripts -- produce no topic and no claim event, deliberately: a
    catch-all "other" bucket dilutes every concentration metric computed over it.
    """
    roots = source_dirs if source_dirs is not None else {"src", "lib", "apps", "pkg"}

    def topics_for_path(path: str) -> list[str]:
        parts = Path(path).parts
        if not parts:
            return []
        head = parts[0]
        if head in _NON_TOPIC or head.startswith("."):
            return []
        if head in roots and len(parts) >= 2:
            second = parts[1]
            # src/<pkg>/<topic>/... -- step past a single packaging directory.
            if len(parts) >= 3 and second not in _NON_TOPIC:
                return [f"{second}/{parts[2]}"] if len(parts) > 3 else [second]
            return [second]
        if len(parts) == 1:
            return []  # a root-level file is not a subsystem
        return [head]

    return topics_for_path


class GitConnector:
    """Read-only access to one repository's history."""

    def __init__(self, repo_root: str | Path) -> None:
        self.repo_root = Path(repo_root).resolve()
        if not (self.repo_root / ".git").exists():
            raise ValueError(f"not a git repository: {self.repo_root}")

    def _git(self, args: list[str]) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=str(self.repo_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
        return result.stdout

    def default_ref(self) -> str:
        for ref in ("main", "master", "HEAD"):
            try:
                self._git(["rev-parse", "--verify", ref])
                return ref
            except subprocess.CalledProcessError:
                continue
        return "HEAD"

    def log(self, ref: Optional[str] = None) -> list[Commit]:
        """Full commit metadata, oldest first, in one git call."""
        ref = ref or self.default_ref()
        fmt = f"%H{_US}%an{_US}%ae{_US}%aI{_US}%s{_US}%B{_RS}"
        out = self._git(["log", ref, "--reverse", f"--pretty=format:{fmt}"])
        commits: list[Commit] = []
        for block in out.split(_RS):
            block = block.strip("\n")
            if not block:
                continue
            try:
                sha, name, email, ts, subject, body = block.split(_US, 5)
            except ValueError:
                continue
            commits.append(
                Commit(
                    sha=sha,
                    author_name=name,
                    author_email=email,
                    timestamp=ts,
                    subject=subject,
                    body=body,
                )
            )
        return commits

    def files_for(self, sha: str) -> tuple[str, ...]:
        out = self._git(
            ["show", "--pretty=format:", "--name-only", "--no-renames", sha]
        )
        return tuple(line.strip() for line in out.splitlines() if line.strip())

    def claim_events(
        self,
        ref: Optional[str] = None,
        *,
        topic_fn: Optional[Callable] = None,
        normalize_identities: bool = True,
    ) -> list[ClaimEvent]:
        """History into claim events, ready for the asymmetry metrics.

        `normalize_identities=False` reproduces the upstream prototype's behaviour
        (raw author name as agent id) and exists so the two can be compared.
        """
        topic_fn = topic_fn or default_topic_fn(self.repo_root)
        commits = [c for c in self.log(ref)]
        commits = [
            Commit(**{**c.__dict__, "files": self.files_for(c.sha)}) for c in commits
        ]
        by_sha = {c.sha: c for c in commits}

        if normalize_identities:
            resolved = resolve_identities((c.author_name, c.author_email) for c in commits)

            def agent_of(c: Commit) -> str:
                return resolved.get(
                    (c.author_name.strip(), _normalize_email(c.author_email)),
                    _normalize_email(c.author_email),
                )
        else:
            def agent_of(c: Commit) -> str:
                return c.author_name

        events: list[ClaimEvent] = []
        for c in commits:
            touched = sorted({t for f in c.files for t in topic_fn(f)})
            for topic in touched:
                events.append(
                    ClaimEvent(
                        topic=topic,
                        agent_id=agent_of(c),
                        is_accepted=True,
                        score=len(c.files),
                        sha=c.sha,
                        timestamp=c.timestamp,
                        subject=c.subject,
                        kind="commit",
                    )
                )

            revert = _REVERTS_COMMIT_RE.search(c.body)
            if _REVERT_SUBJECT_RE.match(c.subject) and revert:
                original = _find_by_prefix(by_sha, revert.group(1))
                if original is not None:
                    original_topics = sorted(
                        {t for f in original.files for t in topic_fn(f)}
                    )
                    for topic in original_topics or touched:
                        events.append(
                            ClaimEvent(
                                topic=topic,
                                agent_id=agent_of(original),
                                is_accepted=False,
                                score=0,
                                sha=c.sha,
                                timestamp=c.timestamp,
                                subject=f"[revert of {original.sha[:8]}] {c.subject}",
                                kind="revert",
                            )
                        )
        return events


def _find_by_prefix(by_sha: dict[str, Commit], prefix: str) -> Optional[Commit]:
    if prefix in by_sha:
        return by_sha[prefix]
    matches = [c for sha, c in by_sha.items() if sha.startswith(prefix)]
    return matches[0] if len(matches) == 1 else None
