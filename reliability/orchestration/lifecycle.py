"""The single door for incident state changes.

Before this existed the approval gate ran inside one HTTP route
(`POST /incidents/{id}/transition`). Every engine added after S5 -- remediation,
verification, the loop driver -- changes incident state too, and each would have
had to remember to call the gate. CLAUDE.md 4.5 ("no write path without a passed
approval gate") cannot rest on remembering.

So: every state change in the codebase goes through `Lifecycle.transition`, which
(1) checks the state machine, (2) consults the approval gate, (3) writes the row,
and (4) appends an audit event. The route is now a thin caller of this.

The event log is append-only. It is what the dashboard timeline reads, and it is
the "auditable" in "auditable reliability loop".
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from apps.api.database import IncidentDB, IncidentEventDB
from models.incident import Incident, IncidentStatus
from reliability.orchestration import gate

SYSTEM = "system"


class InvalidTransition(ValueError):
    """The state machine has no such edge."""


def _now() -> datetime:
    # Stored naive-UTC like every other column in this schema (SQLite has no tz).
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_model(row: IncidentDB) -> Incident:
    return Incident(
        id=row.id,
        repository=row.repository,
        branch=row.branch,
        type=row.type,
        severity=row.severity,
        status=row.status,
        attempt=row.attempt or 1,
        description=row.description,
        metadata=row.metadata_json or {},
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def incident_view(row: IncidentDB) -> dict:
    """The incident as it goes into a prompt: identity and symptoms, nothing internal."""
    return {
        "id": row.id, "repository": row.repository, "type": row.type,
        "severity": row.severity, "description": row.description,
        "metadata": row.metadata_json or {},
    }


class Lifecycle:
    def __init__(self, db: Session) -> None:
        self._db = db

    # ── state changes ────────────────────────────────────────────────────────

    def transition(
        self,
        incident: IncidentDB,
        target: IncidentStatus | str,
        *,
        actor: str = SYSTEM,
        detail: Optional[dict[str, Any]] = None,
    ) -> IncidentDB:
        """Move `incident` to `target` or raise. Never partially applies."""
        try:
            target = IncidentStatus(target) if isinstance(target, str) else target
        except ValueError as exc:
            raise InvalidTransition(str(exc)) from exc

        model = to_model(incident)
        before = model.status
        try:
            model.transition(target)  # state machine
        except ValueError as exc:
            raise InvalidTransition(str(exc)) from exc

        gate.assert_can_enter(self._db, incident.id, target)  # raises GateViolation

        incident.status = model.status.value
        incident.updated_at = model.updated_at
        self.record(
            incident.id,
            "transition",
            actor=actor,
            from_status=before.value,
            to_status=target.value,
            detail=detail,
        )
        return incident

    def bump_attempt(self, incident: IncidentDB) -> int:
        """Start the next pass of the reliability loop. The cap is enforced by the caller
        (reliability.orchestration.loop) because the cap is policy, not schema."""
        incident.attempt = (incident.attempt or 1) + 1
        return incident.attempt

    # ── audit log ────────────────────────────────────────────────────────────

    def record(
        self,
        incident_id: str,
        kind: str,
        *,
        actor: str = SYSTEM,
        from_status: Optional[str] = None,
        to_status: Optional[str] = None,
        detail: Optional[dict[str, Any]] = None,
    ) -> IncidentEventDB:
        event = IncidentEventDB(
            incident_id=incident_id,
            kind=kind,
            actor=actor,
            from_status=from_status,
            to_status=to_status,
            detail=detail or {},
            created_at=_now(),
        )
        self._db.add(event)
        self._db.flush()
        return event

    def timeline(self, incident_id: str) -> list[IncidentEventDB]:
        return (
            self._db.query(IncidentEventDB)
            .filter(IncidentEventDB.incident_id == incident_id)
            .order_by(IncidentEventDB.id)
            .all()
        )
