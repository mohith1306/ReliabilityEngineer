from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from apps.api.database import get_db, generate_id, InvestigationDB, EvidenceDB
from models.investigation import Investigation, InvestigationCreate, Evidence, EvidenceCreate, InvestigationStatus

router = APIRouter()


@router.post("", response_model=Investigation, status_code=201)
def create_investigation(inv: InvestigationCreate, db: Session = Depends(get_db)):
    db_inv = InvestigationDB(
        id=generate_id(),
        incident_id=inv.incident_id,
        status=InvestigationStatus.PENDING.value,
        created_at=datetime.utcnow(),
    )
    db.add(db_inv)
    db.commit()
    db.refresh(db_inv)
    return _to_model(db_inv)


@router.get("", response_model=list[Investigation])
def list_investigations(incident_id: str = None, db: Session = Depends(get_db)):
    query = db.query(InvestigationDB)
    if incident_id:
        query = query.filter(InvestigationDB.incident_id == incident_id)
    invs = query.order_by(InvestigationDB.created_at.desc()).all()
    return [_to_model(i) for i in invs]


@router.get("/{investigation_id}", response_model=Investigation)
def get_investigation(investigation_id: str, db: Session = Depends(get_db)):
    db_inv = db.query(InvestigationDB).filter(InvestigationDB.id == investigation_id).first()
    if not db_inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return _to_model(db_inv)


@router.get("/{investigation_id}/evidence", response_model=list[Evidence])
def get_evidence(investigation_id: str, db: Session = Depends(get_db)):
    evidence = db.query(EvidenceDB).filter(EvidenceDB.investigation_id == investigation_id).all()
    return [_evidence_to_model(e) for e in evidence]


@router.post("/{investigation_id}/evidence", response_model=Evidence, status_code=201)
def add_evidence(investigation_id: str, ev: EvidenceCreate, db: Session = Depends(get_db)):
    db_ev = EvidenceDB(
        id=generate_id(),
        investigation_id=investigation_id,
        source_type=ev.source_type.value,
        source_reference=ev.source_reference,
        content=ev.content,
        relevance_score=ev.relevance_score,
        confidence=ev.confidence,
        created_at=datetime.utcnow(),
    )
    db.add(db_ev)
    db.commit()
    db.refresh(db_ev)
    return _evidence_to_model(db_ev)


@router.post("/{investigation_id}/complete", response_model=Investigation)
def complete_investigation(investigation_id: str, summary: str = "", db: Session = Depends(get_db)):
    db_inv = db.query(InvestigationDB).filter(InvestigationDB.id == investigation_id).first()
    if not db_inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    db_inv.status = InvestigationStatus.COMPLETED.value
    db_inv.summary = summary
    db_inv.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(db_inv)
    return _to_model(db_inv)


def _to_model(db_inv: InvestigationDB) -> Investigation:
    return Investigation(
        id=db_inv.id,
        incident_id=db_inv.incident_id,
        status=db_inv.status,
        summary=db_inv.summary,
        started_at=db_inv.started_at,
        completed_at=db_inv.completed_at,
        created_at=db_inv.created_at,
    )


def _evidence_to_model(db_ev: EvidenceDB) -> Evidence:
    return Evidence(
        id=db_ev.id,
        investigation_id=db_ev.investigation_id,
        source_type=db_ev.source_type,
        source_reference=db_ev.source_reference,
        content=db_ev.content,
        relevance_score=db_ev.relevance_score,
        confidence=db_ev.confidence,
        created_at=db_ev.created_at,
    )
