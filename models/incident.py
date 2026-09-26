from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class IncidentType(str, Enum):
    TEST_FAILURE = "test_failure"
    CI_FAILURE = "ci_failure"
    RUNTIME_ERROR = "runtime_error"
    PERFORMANCE = "performance"
    DEPENDENCY = "dependency"


class IncidentStatus(str, Enum):
    DETECTED = "DETECTED"
    INVESTIGATING = "INVESTIGATING"
    DIAGNOSED = "DIAGNOSED"
    RISK_ASSESSED = "RISK_ASSESSED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    REMEDIATING = "REMEDIATING"
    VERIFYING = "VERIFYING"
    RESOLVED = "RESOLVED"
    REINVESTIGATING = "REINVESTIGATING"
    FAILED = "FAILED"          # an engine broke; retrying the same step will not help
    ABANDONED = "ABANDONED"    # the reliability loop hit its attempt cap (ERRATA A4)
    CLOSED = "CLOSED"


# ERRATA A5: the original table had one happy path and no way out. Every non-terminal
# state now has an exit that is not "succeed", and a false alarm can be closed.
VALID_TRANSITIONS = {
    IncidentStatus.DETECTED: [IncidentStatus.INVESTIGATING, IncidentStatus.CLOSED],
    IncidentStatus.INVESTIGATING: [IncidentStatus.DIAGNOSED, IncidentStatus.FAILED],
    IncidentStatus.DIAGNOSED: [IncidentStatus.RISK_ASSESSED, IncidentStatus.FAILED],
    IncidentStatus.RISK_ASSESSED: [IncidentStatus.AWAITING_APPROVAL, IncidentStatus.REMEDIATING],
    IncidentStatus.AWAITING_APPROVAL: [IncidentStatus.REMEDIATING, IncidentStatus.CLOSED],
    IncidentStatus.REMEDIATING: [
        IncidentStatus.VERIFYING, IncidentStatus.REINVESTIGATING, IncidentStatus.FAILED,
    ],
    IncidentStatus.VERIFYING: [
        IncidentStatus.RESOLVED, IncidentStatus.REINVESTIGATING, IncidentStatus.ABANDONED,
    ],
    IncidentStatus.REINVESTIGATING: [IncidentStatus.INVESTIGATING, IncidentStatus.ABANDONED],
    IncidentStatus.RESOLVED: [IncidentStatus.CLOSED],
    IncidentStatus.FAILED: [IncidentStatus.CLOSED],
    IncidentStatus.ABANDONED: [IncidentStatus.CLOSED],
    IncidentStatus.CLOSED: [],
}

TERMINAL_STATUSES = frozenset({
    IncidentStatus.RESOLVED, IncidentStatus.FAILED, IncidentStatus.ABANDONED, IncidentStatus.CLOSED,
})


class IncidentBase(BaseModel):
    repository: str
    branch: str = "main"
    type: IncidentType
    severity: str = "unknown"
    description: str
    metadata: dict = Field(default_factory=dict)


class IncidentCreate(IncidentBase):
    pass


class Incident(IncidentBase):
    id: str
    status: IncidentStatus = IncidentStatus.DETECTED
    attempt: int = 1  # which pass through the reliability loop; capped (ERRATA A4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def transition(self, new_status: IncidentStatus) -> None:
        allowed = VALID_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Invalid transition: {self.status.value} → {new_status.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )
        self.status = new_status
        self.updated_at = datetime.utcnow()
