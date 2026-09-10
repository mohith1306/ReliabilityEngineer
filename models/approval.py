from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ApprovalDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ApprovalCreate(BaseModel):
    incident_id: str
    risk_level: str
    decision: ApprovalDecision
    approved_by: str
    reason: Optional[str] = None


class Approval(ApprovalCreate):
    id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
