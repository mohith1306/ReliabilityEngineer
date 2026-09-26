from enum import Enum
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class ApprovalDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ApprovalCreate(BaseModel):
    """Wire contract: identity is NEVER supplied by the caller. The bearer
    API key resolves the operator (ERRATA A6)."""

    decision: ApprovalDecision
    reason: Optional[str] = None


class Approval(ApprovalCreate):
    id: str
    incident_id: str
    risk_level: str
    operator_id: str
    operator_name: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
