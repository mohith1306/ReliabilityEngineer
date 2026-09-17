"""Outcome records -- the ledger that closes prediction -> verified result.

See ADR-0003. This is the substrate the learning loop consumes and the metrics of
ARCHITECTURE.md section 30 are computed from. Without it, BRE produces predictions it
can never grade.

Design rules, all from ADR-0003:
    1. A record is opened at PREDICTION time with status=pending. Never reconstructed.
    2. Only reliability.verification may move it to a terminal status (ASMOS Inv 3).
    3. `components` is mandatory on any scored prediction (ASMOS Inv 8).
    4. tenant_id and the cost fields are populated from the first write even while the
       MVP is single-tenant -- neither can be backfilled (ERRATA A7, A8).
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    """UTC now. `datetime.utcnow()` is deprecated in 3.12+ and returns a naive value."""
    return datetime.now(timezone.utc)


class PredictionType(str, Enum):
    """What kind of claim is being graded."""

    DIAGNOSIS = "diagnosis"          # a root-cause hypothesis
    RISK_LEVEL = "risk_level"        # a risk classification
    ROUTING = "routing"              # which source to consult
    REMEDIATION_PLAN = "remediation_plan"


class ClaimClass(str, Enum):
    """ASMOS claim taxonomy, mapped onto reliability engineering.

    Governs how much a verified or refuted outcome moves a source's reputation.
    """

    A = "A"  # objective -- a reproduced failure, a deterministic test result
    B = "B"  # derived   -- an inferred cause, reasoned from evidence
    C = "C"  # subjective -- speculation. NEVER moves reputation.


class OutcomeStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REFUTED = "refuted"
    ABANDONED = "abandoned"  # loop hit its attempt cap, or the incident was closed unresolved


TERMINAL_STATUSES = frozenset(
    {OutcomeStatus.CONFIRMED, OutcomeStatus.REFUTED, OutcomeStatus.ABANDONED}
)


class OutcomeRecordCreate(BaseModel):
    """Opened at prediction time. Everything here is knowable before verification."""

    tenant_id: str = "default"
    incident_id: str
    predictor_id: str = Field(
        description="The diagnosis source: an agent id, a human, an analyzer, a prior incident."
    )
    topic: str = Field(description="Component / subsystem this prediction is about.")
    prediction_type: PredictionType
    prediction_payload: dict = Field(default_factory=dict)
    claim_class: ClaimClass = ClaimClass.B
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    components: dict = Field(
        default_factory=dict,
        description="Score breakdown behind `confidence`. Mandatory for scored "
        "predictions -- a bare scalar is unauditable (ASMOS Invariant 8).",
    )
    attempt_number: int = Field(
        default=1, ge=1, description="Which pass through the reliability loop produced this."
    )


class OutcomeRecord(OutcomeRecordCreate):
    id: str
    status: OutcomeStatus = OutcomeStatus.PENDING
    predicted_at: datetime = Field(default_factory=_utcnow)

    closed_at: Optional[datetime] = None
    closed_by: Optional[str] = Field(
        default=None, description="Verifier identity. Never an agent's self-report."
    )
    verification_run_id: Optional[str] = None

    cost_tokens: int = Field(default=0, description="Tokens spent producing this prediction.")
    cost_wall_ms: float = Field(default=0.0)

    @property
    def is_closed(self) -> bool:
        return self.status in TERMINAL_STATUSES

    @property
    def moves_reputation(self) -> bool:
        """Class C never moves reputation; an open record never moves it either.

        ASMOS Invariant 3: generation changes nothing, verification changes everything.
        """
        return self.is_closed and self.claim_class is not ClaimClass.C

    def close(
        self,
        status: OutcomeStatus,
        *,
        closed_by: str,
        verification_run_id: Optional[str] = None,
    ) -> None:
        """Close the record. Callable only from reliability.verification (ADR-0003).

        Raises if the status is not terminal, or if the record is already closed --
        a ledger that can be silently rewritten is not a ledger.
        """
        if status not in TERMINAL_STATUSES:
            raise ValueError(
                f"{status.value} is not terminal; expected one of "
                f"{sorted(s.value for s in TERMINAL_STATUSES)}"
            )
        if self.is_closed:
            raise ValueError(
                f"outcome {self.id} is already {self.status.value}; "
                "corrections supersede, they do not overwrite"
            )
        self.status = status
        self.closed_by = closed_by
        self.verification_run_id = verification_run_id
        self.closed_at = _utcnow()
