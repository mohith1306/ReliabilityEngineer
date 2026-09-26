"""Promote verified outcomes into durable engineering memory. Stage S8.

DERIVED FROM: ARCHITECTURE.md section 9 and ASMOS's checkpoint lifecycle.

    candidate -> verified outcome -> memory

Quality rule (section 9): do NOT promote uncertain hypotheses into permanent knowledge. The only
thing that triggers consolidation is a PASSED verification run; the only thing consolidated is a
diagnosis that run confirmed. An unverified diagnosis is never consolidated, however confident
the model was -- and `MemoryStore.put_verified` re-checks that independently of this caller.

A diagnosis that was itself *served from memory* is not consolidated again: the knowledge is
already there, and its reuse is recorded where reputation is computed -- the ledger.

ASMOS's own forgetting/lifecycle logic is off by default and not wired to a continuous loop, so
continuous forgetting is out of scope here too rather than inheriting an untested path.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from apps.api.database import DiagnosisDB, IncidentDB, OutcomeRecordDB, VerificationDB
from asmos_bridge.memory.store import MemoryEntry, MemoryStore
from asmos_bridge.ownership.ledger import source_name
from models.outcome import PredictionType
from asmos_bridge.memory.signature import failure_signature
from reliability.orchestration.lifecycle import latest_evidence, to_model

MEMORY_SOURCE = "memory"


def incident_keywords(incident: IncidentDB, evidence: list[dict] | None = None, db: Session | None = None) -> list[str]:
    """The similarity basis: the failure signature -- the incident's analysed keywords plus the tokens of
    the failing test ids in its evidence (see asmos_bridge/memory/signature.py)."""
    if evidence is None:
        evidence = latest_evidence(db, incident.id) if db is not None else []
    return failure_signature(to_model(incident), evidence)


def consolidate(db: Session, incident: IncidentDB, verification: VerificationDB) -> Optional[MemoryEntry]:
    if verification.status != "passed" or verification.incident_id != incident.id:
        return None

    confirmed = (
        db.query(OutcomeRecordDB)
        .filter(
            OutcomeRecordDB.incident_id == incident.id,
            OutcomeRecordDB.prediction_type == PredictionType.DIAGNOSIS.value,
            OutcomeRecordDB.status == "confirmed",
            OutcomeRecordDB.verification_run_id == verification.id,
        )
        .order_by(OutcomeRecordDB.predicted_at.desc())
        .first()
    )
    if confirmed is None:
        return None  # nothing verified to promote
    if source_name(confirmed.predictor_id) == MEMORY_SOURCE:
        return None  # already known; its reuse is recorded in the ledger, not duplicated here

    diagnosis = (
        db.query(DiagnosisDB).filter(DiagnosisDB.incident_id == incident.id)
        .order_by(DiagnosisDB.created_at.desc(), DiagnosisDB.id.desc()).first()
    )
    if diagnosis is None:
        return None

    topic = confirmed.topic
    # Similarity is failure-to-failure ("this looks like that earlier incident"), so the memory's keywords
    # are the incident's own failure signature. Adding the diagnosis's component names would dilute the
    # cosine even for a duplicate incident and push cold-start reuse up against tau.
    keywords = set(incident_keywords(incident, db=db))
    return MemoryStore(db).put_verified(
        topic=topic,
        root_cause=diagnosis.root_cause,
        affected_components=diagnosis.affected_components or [],
        assumptions=diagnosis.assumptions or [],
        keywords=keywords,
        source_incident_id=incident.id,
        source_predictor=source_name(confirmed.predictor_id),
        verification_run_id=verification.id,
        confidence=confirmed.confidence,
    )
