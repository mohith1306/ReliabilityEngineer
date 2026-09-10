from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskAssessmentCreate(BaseModel):
    incident_id: str
    risk_level: RiskLevel
    confidence: float = Field(ge=0.0, le=1.0)
    factors: dict = Field(default_factory=dict)
    blast_radius: int = 0
    affected_components: list[str] = Field(default_factory=list)
    api_surface_affected: bool = False
    database_migration: bool = False
    tests_available: str = "none"


class RiskAssessment(RiskAssessmentCreate):
    id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
