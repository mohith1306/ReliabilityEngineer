import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import create_engine, Column, String, Float, DateTime, JSON, Integer, Boolean, Text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

DATABASE_URL = "sqlite:///./bre.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def generate_id() -> str:
    return uuid.uuid4().hex[:12]


class IncidentDB(Base):
    __tablename__ = "incidents"

    id = Column(String, primary_key=True)
    repository = Column(String, nullable=False)
    branch = Column(String, default="main")
    type = Column(String, nullable=False)
    severity = Column(String, default="unknown")
    status = Column(String, default="DETECTED")
    description = Column(Text, nullable=False)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class InvestigationDB(Base):
    __tablename__ = "investigations"

    id = Column(String, primary_key=True)
    incident_id = Column(String, nullable=False)
    status = Column(String, default="pending")
    summary = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class EvidenceDB(Base):
    __tablename__ = "evidence"

    id = Column(String, primary_key=True)
    investigation_id = Column(String, nullable=False)
    source_type = Column(String, nullable=False)
    source_reference = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    relevance_score = Column(Float, default=0.0)
    confidence = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


class DiagnosisDB(Base):
    __tablename__ = "diagnoses"

    id = Column(String, primary_key=True)
    incident_id = Column(String, nullable=False)
    root_cause = Column(Text, nullable=False)
    confidence = Column(Float, default=0.0)
    affected_components = Column(JSON, default=list)
    evidence_ids = Column(JSON, default=list)
    assumptions = Column(JSON, default=list)
    unresolved_uncertainty = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)


class RiskAssessmentDB(Base):
    __tablename__ = "risk_assessments"

    id = Column(String, primary_key=True)
    incident_id = Column(String, nullable=False)
    risk_level = Column(String, nullable=False)
    confidence = Column(Float, default=0.0)
    factors = Column(JSON, default=dict)
    blast_radius = Column(Integer, default=0)
    affected_components = Column(JSON, default=list)
    api_surface_affected = Column(Boolean, default=False)
    database_migration = Column(Boolean, default=False)
    tests_available = Column(String, default="none")
    created_at = Column(DateTime, default=datetime.utcnow)


class ApprovalDB(Base):
    __tablename__ = "approvals"

    id = Column(String, primary_key=True)
    incident_id = Column(String, nullable=False)
    risk_level = Column(String, nullable=False)
    decision = Column(String, nullable=False)
    approved_by = Column(String, nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class RemediationDB(Base):
    __tablename__ = "remediations"

    id = Column(String, primary_key=True)
    incident_id = Column(String, nullable=False)
    status = Column(String, default="pending")
    summary = Column(Text, default="")
    patch_reference = Column(String, nullable=True)
    changed_files = Column(JSON, default=list)
    tests_added = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class VerificationDB(Base):
    __tablename__ = "verification_runs"

    id = Column(String, primary_key=True)
    incident_id = Column(String, nullable=False)
    remediation_id = Column(String, nullable=False)
    status = Column(String, default="pending")
    tests_run = Column(Integer, default=0)
    tests_passed = Column(Integer, default=0)
    tests_failed = Column(Integer, default=0)
    regressions = Column(JSON, default=list)
    test_results = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class EngineeringMemoryDB(Base):
    __tablename__ = "engineering_memory"

    id = Column(String, primary_key=True)
    type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    source_incident_id = Column(String, nullable=True)
    confidence = Column(Float, default=0.0)
    embedding_reference = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)
