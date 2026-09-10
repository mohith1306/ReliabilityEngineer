from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class DiagnosisCreate(BaseModel):
    incident_id: str
    root_cause: str
    confidence: float = Field(ge=0.0, le=1.0)
    affected_components: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unresolved_uncertainty: list[str] = Field(default_factory=list)


class Diagnosis(DiagnosisCreate):
    id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
