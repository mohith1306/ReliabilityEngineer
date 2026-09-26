"""OutcomeLedger -- prediction opened, verification closed. ADR-0003.

Contract (reliability/ledger/__init__.py):
    OutcomeLedger.open(prediction) -> OutcomeRecord          (status=pending)
    OutcomeLedger.close(record_id, status, verification_run_id)

Structural guards (ASMOS Invariant 3 / ADR-0003):
    - open() rejects a scored prediction (confidence > 0) with no `components`
      (ASMOS Invariant 8: a bare scalar is unauditable).
    - confirmed/refuted require a verification_run_id. An `eval:`-prefixed id is
      the evaluation harness of record (corpus runs have no verification_runs row
      pre-S7); any other id must resolve to a real verification_runs row.
    - The model's close() rejects non-terminal statuses and double closes.
    - abandoned needs no run: the loop hitting its attempt cap is a real outcome.

Everything reads and writes through the caller's Session so the harness can run
against an in-memory database while the API runs against bre.db.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from apps.api.database import OutcomeRecordDB, VerificationDB, generate_id
from models.outcome import (
    ClaimClass,
    OutcomeRecord,
    OutcomeRecordCreate,
    OutcomeStatus,
    PredictionType,
)

EVAL_RUN_PREFIX = "eval:"
_TERMINAL_REQUIRING_RUN = frozenset(
    {OutcomeStatus.CONFIRMED, OutcomeStatus.REFUTED}
)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    """SQLite hands back naive datetimes; the contract's clock is UTC-aware."""
    if dt is None or dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=timezone.utc)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_model(row: OutcomeRecordDB) -> OutcomeRecord:
    return OutcomeRecord(
        id=row.id,
        tenant_id=row.tenant_id,
        incident_id=row.incident_id,
        predictor_id=row.predictor_id,
        topic=row.topic,
        prediction_type=PredictionType(row.prediction_type),
        prediction_payload=row.prediction_payload or {},
        claim_class=row.claim_class,
        confidence=row.confidence,
        components=row.components or {},
        attempt_number=row.attempt_number,
        status=OutcomeStatus(row.status),
        predicted_at=_aware(row.predicted_at),
        closed_at=_aware(row.closed_at),
        closed_by=row.closed_by,
        verification_run_id=row.verification_run_id,
        cost_tokens=row.cost_tokens,
        cost_wall_ms=row.cost_wall_ms,
    )


class OutcomeLedger:
    """The ledger. Caller supplies the Session (API or harness)."""

    def __init__(self, db: Session) -> None:
        self._db = db

    # ── open (prediction time) ────────────────────────────────────────────────

    def open(
        self,
        prediction: OutcomeRecordCreate,
        *,
        cost_tokens: int = 0,
        cost_wall_ms: float = 0.0,
        record_id: Optional[str] = None,
    ) -> OutcomeRecord:
        """Open a record at prediction time. Always status=pending (ADR-0003)."""
        if prediction.confidence > 0 and not prediction.components:
            raise ValueError(
                "scored predictions must carry their component breakdown "
                "(ASMOS Invariant 8): a bare confidence scalar is unauditable"
            )
        record = OutcomeRecord(
            id=record_id or generate_id(),
            **prediction.model_dump(),
            status=OutcomeStatus.PENDING,
            predicted_at=_utcnow(),
            cost_tokens=cost_tokens,
            cost_wall_ms=cost_wall_ms,
        )
        row = OutcomeRecordDB(
            id=record.id,
            tenant_id=record.tenant_id,
            incident_id=record.incident_id,
            predictor_id=record.predictor_id,
            topic=record.topic,
            prediction_type=record.prediction_type.value,
            prediction_payload=record.prediction_payload,
            claim_class=record.claim_class.value,
            predicted_at=record.predicted_at.replace(tzinfo=None),
            confidence=record.confidence,
            components=record.components,
            attempt_number=record.attempt_number,
            status=record.status.value,
            closed_at=None,
            closed_by=None,
            verification_run_id=None,
            cost_tokens=record.cost_tokens,
            cost_wall_ms=record.cost_wall_ms,
        )
        self._db.add(row)
        self._db.flush()
        return record

    # ── close (verification time) ─────────────────────────────────────────────

    def close(
        self,
        record_id: str,
        status: OutcomeStatus,
        *,
        closed_by: str,
        verification_run_id: Optional[str] = None,
    ) -> OutcomeRecord:
        """Close one record. Terminal statuses other than `abandoned` need a run."""
        row = self._db.get(OutcomeRecordDB, record_id)
        if row is None:
            raise KeyError(f"outcome record not found: {record_id}")

        if status in _TERMINAL_REQUIRING_RUN:
            if not verification_run_id:
                raise ValueError(
                    f"closing to {status.value} requires a verification_run_id: "
                    "only a verification result may close a record (ADR-0003)"
                )
            if not verification_run_id.startswith(EVAL_RUN_PREFIX):
                if self._db.get(VerificationDB, verification_run_id) is None:
                    raise ValueError(
                        f"verification run {verification_run_id!r} does not exist; "
                        "a record cannot be closed against a run that never happened"
                    )

        record = _to_model(row)
        record.close(
            status,
            closed_by=closed_by,
            verification_run_id=verification_run_id,
        )
        self._persist(row, record)
        self._db.flush()
        return record

    def close_for_verification(
        self,
        incident_id: str,
        verification_run_id: str,
        *,
        passed: bool,
        closed_by: str,
    ) -> list[OutcomeRecord]:
        """Verification closes every pending record for the incident.

        passed=True -> confirmed, passed=False -> refuted. The run must be a real
        verification_runs row: this is the write path ADR-0003 reserves for
        reliability.verification.
        """
        run = self._db.get(VerificationDB, verification_run_id)
        if run is None:
            raise ValueError(f"verification run not found: {verification_run_id}")
        if run.incident_id != incident_id:
            raise ValueError(
                f"verification run {verification_run_id} belongs to incident "
                f"{run.incident_id}, not {incident_id}"
            )

        target = OutcomeStatus.CONFIRMED if passed else OutcomeStatus.REFUTED
        closed: list[OutcomeRecord] = []
        for row in self._db.query(OutcomeRecordDB).filter(
            OutcomeRecordDB.incident_id == incident_id,
            OutcomeRecordDB.status == OutcomeStatus.PENDING.value,
        ):
            record = _to_model(row)
            record.close(
                target, closed_by=closed_by, verification_run_id=verification_run_id
            )
            self._persist(row, record)
            closed.append(record)
        self._db.flush()
        return closed

    def abandon_pending(self, incident_id: str, *, closed_by: str) -> int:
        """Loop-cap / unresolved-close path. No verification run required."""
        n = 0
        for row in self._db.query(OutcomeRecordDB).filter(
            OutcomeRecordDB.incident_id == incident_id,
            OutcomeRecordDB.status == OutcomeStatus.PENDING.value,
        ):
            record = _to_model(row)
            record.close(OutcomeStatus.ABANDONED, closed_by=closed_by)
            self._persist(row, record)
            n += 1
        self._db.flush()
        return n

    # ── read ──────────────────────────────────────────────────────────────────

    def get(self, record_id: str) -> OutcomeRecord:
        row = self._db.get(OutcomeRecordDB, record_id)
        if row is None:
            raise KeyError(f"outcome record not found: {record_id}")
        return _to_model(row)

    def pending_for_incident(self, incident_id: str) -> list[OutcomeRecord]:
        rows = (
            self._db.query(OutcomeRecordDB)
            .filter(
                OutcomeRecordDB.incident_id == incident_id,
                OutcomeRecordDB.status == OutcomeStatus.PENDING.value,
            )
            .order_by(OutcomeRecordDB.predicted_at)
            .all()
        )
        return [_to_model(r) for r in rows]

    # ── internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _persist(row: OutcomeRecordDB, record: OutcomeRecord) -> None:
        row.status = record.status.value
        row.closed_at = (
            record.closed_at.replace(tzinfo=None) if record.closed_at else None
        )
        row.closed_by = record.closed_by
        row.verification_run_id = record.verification_run_id


# ── typed prediction-time openers (the obligation S4/S5/S8 adopt) ──────────────
# Each engine that makes a prediction opens its record through one of these at
# the moment the prediction is made -- never reconstructed afterwards
# (ADR-0003). The package contracts of reliability/diagnosis, reliability/risk
# and asmos_bridge/routing already carry this obligation.


def open_diagnosis_prediction(
    db: Session,
    *,
    incident_id: str,
    predictor_id: str,
    topic: str,
    root_cause: str,
    confidence: float,
    components: dict,
    attempt_number: int = 1,
    cost_tokens: int = 0,
    cost_wall_ms: float = 0.0,
) -> OutcomeRecord:
    """A root-cause hypothesis, opened before anyone knows if it is right."""
    prediction = OutcomeRecordCreate(
        incident_id=incident_id,
        predictor_id=predictor_id,
        topic=topic,
        prediction_type=PredictionType.DIAGNOSIS,
        prediction_payload={"root_cause": root_cause},
        confidence=confidence,
        components=components,
        attempt_number=attempt_number,
    )
    return OutcomeLedger(db).open(
        prediction, cost_tokens=cost_tokens, cost_wall_ms=cost_wall_ms
    )


def open_risk_prediction(
    db: Session,
    *,
    incident_id: str,
    predictor_id: str,
    topic: str,
    risk_level: str,
    confidence: float,
    components: dict,
    attempt_number: int = 1,
    cost_tokens: int = 0,
    cost_wall_ms: float = 0.0,
) -> OutcomeRecord:
    """A risk classification. Closed later by whether remediation regressed."""
    prediction = OutcomeRecordCreate(
        incident_id=incident_id,
        predictor_id=predictor_id,
        topic=topic,
        prediction_type=PredictionType.RISK_LEVEL,
        prediction_payload={"risk_level": risk_level},
        confidence=confidence,
        components=components,
        attempt_number=attempt_number,
    )
    return OutcomeLedger(db).open(
        prediction, cost_tokens=cost_tokens, cost_wall_ms=cost_wall_ms
    )


def open_remediation_prediction(
    db: Session,
    *,
    incident_id: str,
    predictor_id: str,
    topic: str,
    summary: str,
    changed_files: list,
    confidence: float,
    components: dict,
    attempt_number: int = 1,
    cost_tokens: int = 0,
    cost_wall_ms: float = 0.0,
) -> OutcomeRecord:
    """A remediation plan: 'this patch fixes the incident'. Closed only by the test suite."""
    prediction = OutcomeRecordCreate(
        incident_id=incident_id,
        predictor_id=predictor_id,
        topic=topic,
        prediction_type=PredictionType.REMEDIATION_PLAN,
        prediction_payload={"summary": summary, "changed_files": list(changed_files)},
        claim_class=ClaimClass.A,  # a test result is objective: reproduced-failure class
        confidence=confidence,
        components=components,
        attempt_number=attempt_number,
    )
    return OutcomeLedger(db).open(
        prediction, cost_tokens=cost_tokens, cost_wall_ms=cost_wall_ms
    )


def open_routing_prediction(
    db: Session,
    *,
    incident_id: str,
    predictor_id: str,
    topic: str,
    routed_to: str,
    confidence: float,
    components: dict,
    attempt_number: int = 1,
    cost_tokens: int = 0,
    cost_wall_ms: float = 0.0,
) -> OutcomeRecord:
    """A routing decision. Closed later by whether the routed source verified."""
    prediction = OutcomeRecordCreate(
        incident_id=incident_id,
        predictor_id=predictor_id,
        topic=topic,
        prediction_type=PredictionType.ROUTING,
        prediction_payload={"routed_to": routed_to},
        confidence=confidence,
        components=components,
        attempt_number=attempt_number,
    )
    return OutcomeLedger(db).open(
        prediction, cost_tokens=cost_tokens, cost_wall_ms=cost_wall_ms
    )
