from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class RemediationStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class RemediationCreate(BaseModel):
    incident_id: str
    summary: str = ""
    patch_reference: Optional[str] = None


class Remediation(RemediationCreate):
    id: str
    status: RemediationStatus = RemediationStatus.PENDING
    changed_files: list[str] = Field(default_factory=list)
    tests_added: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
