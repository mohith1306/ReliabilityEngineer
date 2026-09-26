"""Read-only views over what BRE has learned: system mode, ownership, the ledger, evaluation results.

Everything here is derived from the outcome ledger or from stamped artifacts. Nothing is a cached
score; ownership is recomputed from verification closures on every request (Invariant 3 by construction).
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api import settings
from apps.api.database import get_db
from asmos_bridge.memory.store import MemoryStore
from asmos_bridge.ownership.ledger import OwnershipTable
from reliability.ledger.query import accuracy_by, cost_rollup

router = APIRouter()
ARTIFACTS = Path(__file__).resolve().parents[3] / "docs" / "artifacts"


@router.get("/system")
def system():
    return settings.snapshot()


@router.get("/ownership")
def ownership(db: Session = Depends(get_db)):
    table = OwnershipTable.from_ledger(db)
    return {
        "standings": [s.as_dict() for s in table.all()],
        "memory": [
            {"id": m.id, "topic": m.topic, "root_cause": m.root_cause, "components": list(m.affected_components),
             "source_incident": m.source_incident_id, "source": m.source_predictor,
             "verification_run": m.verification_run_id, "confidence": m.confidence, "status": m.status,
             "superseded_by": m.superseded_by}
            for m in MemoryStore(db).all()
        ],
        "explanation": ("Ownership(source, topic) = 0.6 x Trust + 0.4 x ContributionShare, computed only from "
                        "ledger closures backed by a real verification run. Trust = (7 + verified_correct) / "
                        "(10 + verified_total). Class-B claims move reputation by half."),
    }


@router.get("/ledger")
def ledger(db: Session = Depends(get_db)):
    return {"accuracy_by_predictor": accuracy_by(db, "predictor_id"),
            "accuracy_by_prediction_type": accuracy_by(db, "prediction_type"),
            "cost": cost_rollup(db)}


@router.get("/results")
def results():
    """The latest stamped comparison per corpus slice (python -m reliability.evaluation.compare)."""
    latest: dict[str, dict] = {}
    for path in sorted(ARTIFACTS.glob("comparison_*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        latest[data.get("slice", path.stem)] = {
            "slice": data.get("slice"), "artifact": path.name, "generated_at": data.get("generated_at"),
            "corpus_size": data.get("corpus_size"), "look_alikes": data.get("look_alikes_in_corpus"),
            "orderings": data.get("orderings"), "tau": data.get("tau"), "tau_source": data.get("tau_source"),
            "bob_mode": data.get("bob_mode"), "findings": data.get("findings", []),
            "aggregate": data.get("result", {}).get("aggregate", {}),
            "paired": data.get("result", {}).get("paired_differences", {}),
            "cost_note": data.get("cost_note"),
        }
    return {"slices": list(latest.values())}
