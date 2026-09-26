"""Risk assessment as a service: classify, persist, and open the ledger prediction.

Extracted from the /assess-risk route so the HTTP route and the reliability loop share one
implementation -- there is exactly one place a risk level is produced and one place its
prediction is opened (ADR-0003 / CLAUDE.md 4: every risk level is a prediction).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from apps.api.database import IncidentDB, RiskAssessmentDB, generate_id
from reliability.ledger.record import open_risk_prediction
from reliability.orchestration.lifecycle import Lifecycle
from reliability.risk.classifier import PREDICTOR_ID, RiskClassifier


def assess_risk(
    db: Session,
    incident: IncidentDB,
    *,
    blast_radius: int = 0,
    api_surface_affected: bool = False,
    database_migration: bool = False,
    tests_available: str = "none",
    affected_components: Iterable[str] = (),
    diagnosis_confidence: Optional[float] = None,
    diagnosis_root_cause: Optional[str] = None,
    topic: Optional[str] = None,
) -> RiskAssessmentDB:
    components = list(affected_components)
    repo_context = {
        "incident_id": incident.id,
        "severity": incident.severity,
        "blast_radius": blast_radius,
        "api_surface_affected": api_surface_affected,
        "database_migration": database_migration,
        "tests_available": tests_available,
        "affected_components": components,
    }
    diagnosis = None
    if diagnosis_confidence is not None or diagnosis_root_cause:
        diagnosis = {
            "incident_id": incident.id,
            "root_cause": diagnosis_root_cause or "",
            "confidence": diagnosis_confidence or 0.0,
        }

    assessment = RiskClassifier().classify(diagnosis, repo_context)

    row = RiskAssessmentDB(
        id=generate_id(),
        incident_id=incident.id,
        risk_level=assessment.risk_level.value,
        confidence=assessment.confidence,
        factors=assessment.factors,
        blast_radius=assessment.blast_radius,
        affected_components=assessment.affected_components,
        api_surface_affected=assessment.api_surface_affected,
        database_migration=assessment.database_migration,
        tests_available=assessment.tests_available,
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    open_risk_prediction(
        db,
        incident_id=incident.id,
        predictor_id=PREDICTOR_ID,
        topic=topic or incident.type,
        risk_level=assessment.risk_level.value,
        confidence=assessment.confidence,
        components=assessment.factors,
        attempt_number=incident.attempt or 1,
    )
    Lifecycle(db).record(
        incident.id, "risk", actor=PREDICTOR_ID,
        detail={"level": assessment.risk_level.value, "score": assessment.factors.get("score"),
                "attempt": incident.attempt or 1},
    )
    db.flush()
    return row
