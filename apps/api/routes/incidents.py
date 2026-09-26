from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from apps.api.database import get_db, generate_id, EvidenceDB, IncidentDB, InvestigationDB
from apps.api.services import investigation_service
from models.incident import IncidentCreate, Incident, IncidentStatus

router = APIRouter()


class InvestigateRequest(BaseModel):
    repo_path: str | None = Field(
        default=None,
        description="Filesystem root of the target repository. Overrides incident metadata.",
    )
    run_tests: bool = Field(
        default=False,
        description="Run the target's test suite as part of evidence collection.",
    )


class EvidenceOut(BaseModel):
    id: str
    investigation_id: str
    source_type: str
    source_reference: str
    content: str
    relevance_score: float
    confidence: float


class InvestigateResponse(BaseModel):
    incident_id: str
    investigation: dict
    evidence: list[EvidenceOut]


@router.post("", response_model=Incident, status_code=201)
def create_incident(incident: IncidentCreate, db: Session = Depends(get_db)):
    db_incident = IncidentDB(
        id=generate_id(),
        repository=incident.repository,
        branch=incident.branch,
        type=incident.type.value,
        severity=incident.severity,
        status=IncidentStatus.DETECTED.value,
        description=incident.description,
        metadata_json=incident.metadata,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(db_incident)
    db.commit()
    db.refresh(db_incident)
    return _to_model(db_incident)


@router.get("", response_model=list[Incident])
def list_incidents(
    status: str = None,
    repository: str = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    query = db.query(IncidentDB)
    if status:
        query = query.filter(IncidentDB.status == status)
    if repository:
        query = query.filter(IncidentDB.repository == repository)
    incidents = query.order_by(IncidentDB.created_at.desc()).offset(skip).limit(limit).all()
    return [_to_model(i) for i in incidents]


@router.get("/{incident_id}", response_model=Incident)
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    db_incident = db.query(IncidentDB).filter(IncidentDB.id == incident_id).first()
    if not db_incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return _to_model(db_incident)


@router.post("/{incident_id}/transition", response_model=Incident)
def transition_incident(incident_id: str, new_status: str, db: Session = Depends(get_db)):
    db_incident = db.query(IncidentDB).filter(IncidentDB.id == incident_id).first()
    if not db_incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident = _to_model(db_incident)
    try:
        target_status = IncidentStatus(new_status)
        incident.transition(target_status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db_incident.status = incident.status.value
    db_incident.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_incident)
    return _to_model(db_incident)


@router.post("/{incident_id}/investigate", response_model=InvestigateResponse)
def investigate_incident(
    incident_id: str,
    body: InvestigateRequest | None = None,
    db: Session = Depends(get_db),
):
    """Drive DETECTED -> INVESTIGATING, collect evidence, return the package."""
    db_incident = db.query(IncidentDB).filter(IncidentDB.id == incident_id).first()
    if not db_incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    req = body or InvestigateRequest()
    try:
        investigation, evidence_rows, incident_row = investigation_service.run_investigation(
            db, db_incident, repo_path=req.repo_path, run_tests=req.run_tests,
        )
    except investigation_service.RepoRootUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    db.commit()
    db.refresh(investigation)
    db.refresh(incident_row)

    return InvestigateResponse(
        incident_id=incident_id,
        investigation={
            "id": investigation.id,
            "incident_id": investigation.incident_id,
            "status": investigation.status,
            "summary": investigation.summary,
            "started_at": investigation.started_at,
            "completed_at": investigation.completed_at,
        },
        evidence=[
            EvidenceOut(
                id=e.id,
                investigation_id=e.investigation_id,
                source_type=e.source_type,
                source_reference=e.source_reference,
                content=e.content,
                relevance_score=e.relevance_score,
                confidence=e.confidence,
            )
            for e in evidence_rows
        ],
    )


def _to_model(db_incident: IncidentDB) -> Incident:
    return Incident(
        id=db_incident.id,
        repository=db_incident.repository,
        branch=db_incident.branch,
        type=db_incident.type,
        severity=db_incident.severity,
        status=db_incident.status,
        description=db_incident.description,
        metadata=db_incident.metadata_json or {},
        created_at=db_incident.created_at,
        updated_at=db_incident.updated_at,
    )
