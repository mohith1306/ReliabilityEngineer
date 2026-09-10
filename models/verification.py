from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class VerificationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"


class TestResult(BaseModel):
    name: str
    status: str
    duration_ms: float = 0.0
    error: Optional[str] = None


class VerificationCreate(BaseModel):
    incident_id: str
    remediation_id: str


class Verification(VerificationCreate):
    id: str
    status: VerificationStatus = VerificationStatus.PENDING
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    regressions: list[str] = Field(default_factory=list)
    test_results: list[TestResult] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
