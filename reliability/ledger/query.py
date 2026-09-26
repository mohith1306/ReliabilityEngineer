"""Ledger rollups -- the inputs to ARCHITECTURE.md section 30 metrics.

Contract (reliability/ledger/__init__.py):
    Accuracy, calibration and cost rollups per source, per topic, per risk level.

Only closed records count as evidence; `abandoned` is reported separately and
stays out of the accuracy denominator (it says the loop stopped, not that the
prediction was wrong).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from apps.api.database import OutcomeRecordDB
from models.outcome import OutcomeStatus

_DIMENSIONS = {
    "predictor_id": OutcomeRecordDB.predictor_id,
    "topic": OutcomeRecordDB.topic,
    "prediction_type": OutcomeRecordDB.prediction_type,
}


def accuracy_by(db: Session, dimension: str = "predictor_id") -> list[dict]:
    """confirmed / (confirmed + refuted) grouped by dimension, plus counts."""
    if dimension not in _DIMENSIONS:
        raise ValueError(
            f"unknown dimension {dimension!r}; expected one of {sorted(_DIMENSIONS)}"
        )
    column = _DIMENSIONS[dimension]
    rows = (
        db.query(column, OutcomeRecordDB.status)
        .filter(OutcomeRecordDB.status != OutcomeStatus.PENDING.value)
        .all()
    )

    buckets: dict[str, dict] = {}
    for value, status in rows:
        bucket = buckets.setdefault(
            value, {"confirmed": 0, "refuted": 0, "abandoned": 0}
        )
        bucket[status] = bucket.get(status, 0) + 1

    results = []
    for value in sorted(buckets):
        counts = buckets[value]
        graded = counts["confirmed"] + counts["refuted"]
        results.append(
            {
                dimension: value,
                "confirmed": counts["confirmed"],
                "refuted": counts["refuted"],
                "abandoned": counts["abandoned"],
                "graded": graded,
                "accuracy": (
                    round(counts["confirmed"] / graded, 4) if graded else None
                ),
            }
        )
    return results


def cost_rollup(db: Session) -> dict:
    """Token and wall-time totals -- ERRATA A8: recorded as it is spent."""
    rows = db.query(OutcomeRecordDB).all()
    by_predictor: dict[str, dict] = {}
    total_tokens = 0
    total_wall_ms = 0.0
    for row in rows:
        total_tokens += row.cost_tokens
        total_wall_ms += row.cost_wall_ms
        bucket = by_predictor.setdefault(
            row.predictor_id, {"records": 0, "cost_tokens": 0, "cost_wall_ms": 0.0}
        )
        bucket["records"] += 1
        bucket["cost_tokens"] += row.cost_tokens
        bucket["cost_wall_ms"] += row.cost_wall_ms
    return {
        "records": len(rows),
        "total_tokens": total_tokens,
        "total_wall_ms": round(total_wall_ms, 3),
        "by_predictor": by_predictor,
    }
