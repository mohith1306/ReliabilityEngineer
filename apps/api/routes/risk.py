"""Risk assessment endpoint: classify, persist, and open the ledger prediction.

Every risk level is a prediction (ADR-0003 / CLAUDE.md 4): it is written to
the outcome ledger as pending at assessment time, with the full factor
breakdown as its components.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from apps.api.database import IncidentDB, RiskAssessmentDB, generate_id, get_db
from models.risk import RiskAssessment
from reliability.risk.classifier import PREDICTOR_ID, RiskClassifier

router = APIRouter()


class RiskContext(BaseModel):
    blast_radius: int = Field(default=0, ge=0)
    api_surface_affected: bool = False
    database_migration: bool = False
    tests_available: str = "none"
    affected_components: list[str] = Field(default_factory=list)
    diagnosis_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    diagnosis_root_cause: Optional[str] = None


@router.post("/{incident_id}/assess-risk", response_model=RiskAssessment, status_code=201)
def assess_risk(
    incident_id: str,
    body: RiskContext | None = None,
    db: Session = Depends(get_db),
):
    incident = db.query(IncidentDB).filter(IncidentDB.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    ctx = body or RiskContext()
    repo_context = {
        "incident_id": incident_id,
        "severity": incident.severity,
        "blast_radius": ctx.blast_radius,
        "api_surface_affected": ctx.api_surface_affected,
        "database_migration": ctx.database_migration,
        "tests_available": ctx.tests_available,
        "affected_components": ctx.affected_components,
    }
    diagnosis = None
    if ctx.diagnosis_confidence is not None or ctx.diagnosis_root_cause:
        diagnosis = {
            "incident_id": incident_id,
            "root_cause": ctx.diagnosis_root_cause or "",
            "confidence": ctx.diagnosis_confidence or 0.0,
        }

    assessment = RiskClassifier().classify(diagnosis, repo_context)

    row = RiskAssessmentDB(
        id=generate_id(),
        incident_id=incident_id,
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

    from reliability.ledger.record import open_risk_prediction

    open_risk_prediction(
        db,
        incident_id=incident_id,
        predictor_id=PREDICTOR_ID,
        topic=incident.type,
        risk_level=assessment.risk_level.value,
        confidence=assessment.confidence,
        components=assessment.factors,
    )
    db.commit()
    db.refresh(row)

    return RiskAssessment(
        id=row.id,
        incident_id=row.incident_id,
        risk_level=row.risk_level,
        confidence=row.confidence,
        factors=row.factors,
        blast_radius=row.blast_radius,
        affected_components=row.affected_components,
        api_surface_affected=row.api_surface_affected,
        database_migration=row.database_migration,
        tests_available=row.tests_available,
        created_at=row.created_at,
    )
