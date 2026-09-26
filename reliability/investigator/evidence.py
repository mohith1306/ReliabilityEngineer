"""EvidenceCollector: pull from connectors into scored evidence items.

Contract (reliability/investigator/__init__.py):
    EvidenceCollector.collect(task) -> list[Evidence]
    Every item carries source_type, source_reference, relevance and confidence.

READ-ONLY: reads the target repository, never writes to it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from connectors.ci import CIConnector
from connectors.git import GitConnector
from connectors.repository import RepositoryConnector
from connectors.tests import TestConnector
from reliability.investigator.analyzer import IncidentTask

logger = logging.getLogger("bre.investigation")

# Confidence per source type: how much a hit from this source is worth on its own.
SOURCE_CONFIDENCE = {
    "ci": 0.95,
    "test": 0.85,
    "git": 0.80,
    "config": 0.75,
    "repository": 0.70,
}

CONFIG_SUFFIXES = {".yaml", ".yml", ".toml", ".cfg", ".ini", ".env", ".json"}
MAX_EVIDENCE_PER_SOURCE = 5
MAX_ERROR_CHARS = 600


@dataclass
class CollectedEvidence:
    source_type: str        # repository | git | test | ci | config | memory
    source_reference: str   # file path, commit sha, test id, log path
    content: str
    relevance: float
    confidence: float


class EvidenceCollector:
    """Collects evidence from the four MVP connectors for one task."""

    def __init__(
        self,
        repository: RepositoryConnector | None = None,
        git: GitConnector | None = None,
        tests: TestConnector | None = None,
        ci: CIConnector | None = None,
    ) -> None:
        self._repository = repository or RepositoryConnector()
        self._git = git or GitConnector()
        self._tests = tests or TestConnector(self._repository)
        self._ci = ci or CIConnector()

    def collect(self, task: IncidentTask, root: str) -> list[CollectedEvidence]:
        evidence: list[CollectedEvidence] = []
        keywords = task.keywords or [task.incident_type]

        evidence.extend(self._from_repository(task, root, keywords))
        evidence.extend(self._from_config(task, root, keywords))
        evidence.extend(self._from_git(task, root, keywords))
        evidence.extend(self._from_tests(task, root, keywords))
        evidence.extend(self._from_ci(task, root))

        evidence.sort(key=lambda e: -e.relevance)
        logger.info(
            "collected %d evidence items for incident %s",
            len(evidence), task.incident_id,
        )
        return evidence

    # ── repository ────────────────────────────────────────────────────────────

    def _from_repository(self, task, root, keywords) -> list[CollectedEvidence]:
        out: list[CollectedEvidence] = []
        path_hits = self._repository.find_files_matching(root, keywords, max_results=MAX_EVIDENCE_PER_SOURCE)

        pattern = "|".join(keywords[:12])
        content_hits = self._repository.files_mentioning(root, pattern, max_results=MAX_EVIDENCE_PER_SOURCE)
        content_map = dict(content_hits)

        seen: set[str] = set()
        for path, path_score in path_hits:
            seen.add(path)
            relevance = max(path_score, content_map.get(path, 0.0))
            out.append(CollectedEvidence(
                source_type="repository",
                source_reference=path,
                content=f"file matched keywords: {', '.join(keywords[:6])}",
                relevance=round(min(1.0, relevance), 3),
                confidence=SOURCE_CONFIDENCE["repository"],
            ))

        for path, content_score in content_hits:
            if path in seen:
                continue
            out.append(CollectedEvidence(
                source_type="repository",
                source_reference=path,
                content=f"content matched search pattern for: {', '.join(keywords[:6])}",
                relevance=round(min(1.0, content_score), 3),
                confidence=SOURCE_CONFIDENCE["repository"],
            ))
        return out

    # ── config ────────────────────────────────────────────────────────────────

    def _from_config(self, task, root, keywords) -> list[CollectedEvidence]:
        """Configuration files are their own source type: score by content hits."""
        from pathlib import Path as _Path

        out: list[CollectedEvidence] = []
        if not keywords:
            return out
        for sf in self._repository.list_files(root):
            suffix = _Path(sf.path).suffix.lower()
            if suffix not in CONFIG_SUFFIXES and "config" not in sf.path.lower():
                continue
            if sf.size > 64 * 1024:
                continue
            try:
                text = self._repository.read_file(root, sf.path, max_bytes=64 * 1024)
            except (OSError, ValueError):
                continue
            haystack = text.lower()
            hits = sum(1 for k in keywords if k in haystack)
            if not hits:
                continue
            out.append(CollectedEvidence(
                source_type="config",
                source_reference=sf.path,
                content=f"configuration mentions {hits} of {len(keywords)} incident keywords",
                relevance=round(min(1.0, 0.4 + 0.15 * hits), 3),
                confidence=SOURCE_CONFIDENCE["config"],
            ))
            if len(out) >= MAX_EVIDENCE_PER_SOURCE:
                break
        return out

    # ── git ───────────────────────────────────────────────────────────────────

    def _from_git(self, task, root, keywords) -> list[CollectedEvidence]:
        out: list[CollectedEvidence] = []
        try:
            matched_paths = [p for p, _ in self._repository.find_files_matching(root, keywords, max_results=5)]
            commits = self._git.log_for_paths(root, matched_paths, limit=3) if matched_paths else []
            if not commits:
                commits = self._git.recent_commits(root, limit=3)
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            logger.info("git history unavailable for %s: %s", root, exc)
            return out

        for commit in commits:
            changed = ", ".join(commit.files_changed[:3]) or "no file stats"
            out.append(CollectedEvidence(
                source_type="git",
                source_reference=f"commit:{commit.short_sha}",
                content=f"{commit.message.splitlines()[0]} (changed: {changed})",
                relevance=0.8 if matched_paths else 0.5,
                confidence=SOURCE_CONFIDENCE["git"],
            ))
        return out

    # ── tests ─────────────────────────────────────────────────────────────────

    def _from_tests(self, task, root, keywords) -> list[CollectedEvidence]:
        out: list[CollectedEvidence] = []
        discovered = self._tests.discover(root)
        if not discovered:
            return out

        keyword_blob = " ".join(keywords)
        matching = [
            t for t in discovered
            if t.name and any(k in (t.name + " " + t.file).lower() for k in keywords[:8])
        ]
        chosen = (matching or discovered)[:MAX_EVIDENCE_PER_SOURCE]

        for t in chosen:
            label = f"{t.file}::{t.name}" if t.name else t.file
            out.append(CollectedEvidence(
                source_type="test",
                source_reference=label,
                content=f"discovered test relevant to: {keyword_blob[:120]}",
                relevance=0.9 if t in matching else 0.5,
                confidence=SOURCE_CONFIDENCE["test"],
            ))

        if task.metadata.get("run_tests"):
            result = self._tests.run(root)
            status = "PASSED" if result.passed else "FAILED"
            failed_names = [c.name for c in result.cases if not c.passed][:5]
            summary = (
                f"test run {status} ({result.command}); "
                f"failures: {', '.join(failed_names) or 'none listed'}"
            )
            out.append(CollectedEvidence(
                source_type="test",
                source_reference=f"run:{result.command}",
                content=summary[:MAX_ERROR_CHARS],
                relevance=1.0,
                confidence=SOURCE_CONFIDENCE["test"] + 0.1,
            ))
        return out

    # ── ci ────────────────────────────────────────────────────────────────────

    def _from_ci(self, task, root) -> list[CollectedEvidence]:
        out: list[CollectedEvidence] = []
        log_path = task.metadata.get("ci_log")
        inline = task.metadata.get("ci_log_text")

        record = None
        if isinstance(inline, str) and inline.strip():
            record = self._ci.parse_text(inline, source="incident.metadata.ci_log_text")
        elif isinstance(log_path, str) and log_path.strip():
            from pathlib import Path as _Path
            p = _Path(log_path)
            if not p.is_absolute():
                p = _Path(root) / log_path
            try:
                record = self._ci.parse_file(str(p))
            except FileNotFoundError as exc:
                logger.info("ci log unavailable: %s", exc)
            else:
                # Store the ref repo-relative with POSIX separators: an absolute path
                # embeds a per-run temp dir (non-reproducible) and, on Windows, "\\".
                try:
                    record.source = p.resolve().relative_to(_Path(root).resolve()).as_posix()
                except ValueError:
                    record.source = p.resolve().as_posix()

        if record is None:
            return out

        if not record.failures:
            out.append(CollectedEvidence(
                source_type="ci",
                source_reference=record.source,
                content=f"CI log parsed: no individual failures found (failed_count={record.failed_count})",
                relevance=0.6,
                confidence=SOURCE_CONFIDENCE["ci"],
            ))
            return out

        for failure in record.failures[:MAX_EVIDENCE_PER_SOURCE]:
            reason = (failure.reason or "").strip()[:MAX_ERROR_CHARS]
            out.append(CollectedEvidence(
                source_type="ci",
                source_reference=f"{record.source}::{failure.reference}",
                content=reason or f"CI reported failure at {failure.reference}",
                relevance=0.95,
                confidence=SOURCE_CONFIDENCE["ci"],
            ))
        return out
