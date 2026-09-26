"""Investigator: orchestrates analysis + evidence collection into a package.

Contract (reliability/investigator/__init__.py):
    Investigator.investigate(incident) -> Investigation
    Orchestrates analyzer + collector; writes evidence rows; never mutates the
    target repository.

Invariant: this module is READ-ONLY with respect to the target repo. The only
writes it performs are evidence rows through the injected store (our own DB).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from models.incident import Incident
from reliability.investigator.analyzer import IncidentTask, TaskAnalyzer
from reliability.investigator.evidence import CollectedEvidence, EvidenceCollector

logger = logging.getLogger("bre.investigation")


class EvidenceStore(Protocol):
    """Persistence for evidence rows. Implemented by the API service layer."""

    def add_evidence(self, investigation_id: str, item: CollectedEvidence) -> str: ...


@dataclass
class InvestigationResult:
    incident_id: str
    task: IncidentTask
    evidence: list[CollectedEvidence] = field(default_factory=list)
    summary: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def source_types(self) -> list[str]:
        seen: list[str] = []
        for item in self.evidence:
            if item.source_type not in seen:
                seen.append(item.source_type)
        return seen

    def to_summary(self) -> str:
        by_type: dict[str, int] = {}
        for item in self.evidence:
            by_type[item.source_type] = by_type.get(item.source_type, 0) + 1
        parts = [f"{n} {t}" for t, n in sorted(by_type.items())]
        topics = ", ".join(self.task.topics[:5]) or "none"
        return (
            f"{len(self.evidence)} evidence items "
            f"({', '.join(parts) or 'none'}); topics: {topics}"
        )


class Investigator:
    """Builds the evidence package for one incident. Read-only on the target."""

    def __init__(
        self,
        analyzer: TaskAnalyzer | None = None,
        collector: EvidenceCollector | None = None,
    ) -> None:
        self._analyzer = analyzer or TaskAnalyzer()
        self._collector = collector or EvidenceCollector()

    def investigate(
        self,
        incident: Incident,
        root: str,
        *,
        investigation_id: str | None = None,
        store: EvidenceStore | None = None,
    ) -> InvestigationResult:
        started = datetime.now(timezone.utc)
        task = self._analyzer.analyze(incident)
        logger.info(
            "investigating incident=%s type=%s root=%s keywords=%d",
            incident.id, task.incident_type, root, len(task.keywords),
        )

        evidence = self._collector.collect(task, root)
        completed = datetime.now(timezone.utc)

        result = InvestigationResult(
            incident_id=incident.id,
            task=task,
            evidence=evidence,
            summary="",
            started_at=started,
            completed_at=completed,
        )
        result.summary = result.to_summary()

        if store is not None and investigation_id is not None:
            for item in evidence:
                store.add_evidence(investigation_id, item)

        logger.info(
            "investigation complete incident=%s evidence=%d sources=%s",
            incident.id, len(evidence), ",".join(result.source_types) or "none",
        )
        return result
