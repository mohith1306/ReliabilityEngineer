"""Approvals: verified operator identity via bearer API key (S5)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from apps.api import auth
from apps.api.database import (
    ApprovalDB,
    IncidentDB,
    RiskAssessmentDB,
    generate_id,
    get_db,
)
from models.approval import Approval, ApprovalCreate

router = APIRouter()


def _latest_risk_level(db: Session, incident_id: str) -> str:
    row = (
        db.query(RiskAssessmentDB)
        .filter(RiskAssessmentDB.incident_id == incident_id)
        .order_by(RiskAssessmentDB.created_at.desc())
        .first()
    )
    return row.risk_level if row else "UNKNOWN"


def _require_incident(db: Session, incident_id: str) -> IncidentDB:
    row = db.query(IncidentDB).filter(IncidentDB.id == incident_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Incident not found")
    return row


@router.post("/{incident_id}/approvals", response_model=Approval, status_code=201)
def create_approval(
    incident_id: str,
    body: ApprovalCreate,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    _require_incident(db, incident_id)
    try:
        operator = auth.authenticate(db, authorization)
    except auth.AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    row = ApprovalDB(
        id=generate_id(),
        incident_id=incident_id,
        risk_level=_latest_risk_level(db, incident_id),
        decision=body.decision.value,
        operator_id=operator.id,
        operator_name=operator.name,
        reason=body.reason,
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return Approval(
        id=row.id,
        incident_id=row.incident_id,
        risk_level=row.risk_level,
        decision=row.decision,
        operator_id=row.operator_id,
        operator_name=row.operator_name,
        reason=row.reason,
        created_at=row.created_at,
    )


@router.get("/{incident_id}/approvals", response_model=list[Approval])
def list_approvals(incident_id: str, db: Session = Depends(get_db)):
    _require_incident(db, incident_id)
    rows = (
        db.query(ApprovalDB)
        .filter(ApprovalDB.incident_id == incident_id)
        .order_by(ApprovalDB.created_at.asc())
        .all()
    )
    return [
        Approval(
            id=r.id,
            incident_id=r.incident_id,
            risk_level=r.risk_level,
            decision=r.decision,
            operator_id=r.operator_id or "",
            operator_name=r.operator_name or "",
            reason=r.reason,
            created_at=r.created_at,
        )
        for r in rows
    ]
