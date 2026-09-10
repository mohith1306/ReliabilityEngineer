from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class EvidenceSource(str, Enum):
    REPOSITORY = "repository"
    GIT = "git"
    TEST = "test"
    CI = "ci"
    CONFIG = "config"
    MEMORY = "memory"


class EvidenceCreate(BaseModel):
    source_type: EvidenceSource
    source_reference: str
    content: str
    relevance_score: float = 0.0
    confidence: float = 0.0


class Evidence(EvidenceCreate):
    id: str
    investigation_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class InvestigationStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class InvestigationCreate(BaseModel):
    incident_id: str


class Investigation(InvestigationCreate):
    id: str
    status: InvestigationStatus = InvestigationStatus.PENDING
    summary: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
