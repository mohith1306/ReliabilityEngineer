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

    from apps.api.services.risk_service import assess_risk as assess

    ctx = body or RiskContext()
    row = assess(
        db, incident,
        blast_radius=ctx.blast_radius,
        api_surface_affected=ctx.api_surface_affected,
        database_migration=ctx.database_migration,
        tests_available=ctx.tests_available,
        affected_components=ctx.affected_components,
        diagnosis_confidence=ctx.diagnosis_confidence,
        diagnosis_root_cause=ctx.diagnosis_root_cause,
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
