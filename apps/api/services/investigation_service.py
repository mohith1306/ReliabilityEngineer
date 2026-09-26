"""Investigation service: resolve the target repo, run the Investigator, persist.

Routes stay thin; the orchestration lives here (CLAUDE.md section 6).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from sqlalchemy.orm import Session

from apps.api.database import EvidenceDB, IncidentDB, InvestigationDB, generate_id
from models.incident import Incident, IncidentStatus
from reliability.investigator.evidence import CollectedEvidence
from reliability.investigator.investigator import Investigator

logger = logging.getLogger("bre.investigation")

# States from which an investigation may start.
STARTABLE = {IncidentStatus.DETECTED, IncidentStatus.INVESTIGATING, IncidentStatus.REINVESTIGATING}


class RepoRootUnavailable(Exception):
    """No filesystem root could be resolved for the incident's repository."""


def resolve_repo_root(incident: Incident, override: str | None = None) -> str:
    """Resolve the repository name to a local filesystem root.

    Order: explicit override -> incident metadata repo_path -> BRE_REPO_ROOT
    env var -> no mapping (error). Keeps one-repo MVP scope honest instead of
    guessing a path.
    """
    candidates: list[str] = []
    if override:
        candidates.append(override)
    meta_path = (incident.metadata or {}).get("repo_path")
    if isinstance(meta_path, str) and meta_path:
        candidates.append(meta_path)
    env_root = os.environ.get("BRE_REPO_ROOT")
    if env_root:
        candidates.append(env_root)

    for cand in candidates:
        p = Path(cand).expanduser()
        if p.is_dir():
            return str(p.resolve())

    raise RepoRootUnavailable(
        f"No filesystem root for repository '{incident.repository}'. "
        "Provide repo_path in the request body or incident metadata, "
        "or set BRE_REPO_ROOT."
    )


class _SQLAlchemyEvidenceStore:
    """EvidenceStore backed by the incidents database."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def add_evidence(self, investigation_id: str, item: CollectedEvidence) -> str:
        row = EvidenceDB(
            id=generate_id(),
            investigation_id=investigation_id,
            source_type=item.source_type,
            source_reference=item.source_reference,
            content=item.content,
            relevance_score=item.relevance,
            confidence=item.confidence,
        )
        self._db.add(row)
        return row.id


def _to_incident_model(row) -> Incident:
    return Incident(
        id=row.id,
        repository=row.repository,
        branch=row.branch,
        type=row.type,
        severity=row.severity,
        status=row.status,
        description=row.description,
        metadata=row.metadata_json or {},
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def run_investigation(
    db: Session,
    incident_row,
    *,
    repo_path: str | None = None,
    run_tests: bool = False,
) -> tuple[InvestigationDB, list[EvidenceDB], IncidentDB]:
    """Drive DETECTED -> INVESTIGATING, collect evidence, complete the investigation.

    Returns (investigation_row, evidence_rows, incident_row).
    Raises RepoRootUnavailable when the target cannot be located, and
    ValueError when the incident is not in a startable state.
    """
    incident = _to_incident_model(incident_row)
    if incident.status not in STARTABLE:
        raise ValueError(
            f"Incident {incident.id} is {incident.status.value}; "
            f"investigation can start from {[s.value for s in STARTABLE]}"
        )

    root = resolve_repo_root(incident, override=repo_path)

    if incident.status == IncidentStatus.DETECTED:
        incident.transition(IncidentStatus.INVESTIGATING)
        incident_row.status = incident.status.value
        incident_row.updated_at = incident.updated_at

    investigation = InvestigationDB(
        id=generate_id(),
        incident_id=incident.id,
        status="in_progress",
        started_at=incident.updated_at,
    )
    db.add(investigation)
    db.flush()

    if run_tests:
        merged = dict(incident.metadata)
        merged["run_tests"] = True
        incident.metadata = merged

    store = _SQLAlchemyEvidenceStore(db)
    investigator = Investigator()
    result = investigator.investigate(
        incident, root, investigation_id=investigation.id, store=store
    )

    investigation.status = "completed"
    investigation.summary = result.summary
    investigation.completed_at = result.completed_at
    db.flush()
    evidence_rows = (
        db.query(EvidenceDB)
        .filter(EvidenceDB.investigation_id == investigation.id)
        .all()
    )
    logger.info(
        "investigation %s finished: %d evidence rows",
        investigation.id, len(evidence_rows),
    )
    return investigation, evidence_rows, incident_row
