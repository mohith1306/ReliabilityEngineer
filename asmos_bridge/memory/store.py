"""Verified engineering memory -- the store the router reads from.

Shaped after the ASMOS memory contract (CONTRACT.md v1.2, `memory/checkpoint.py`) in the parts
that matter here:

  * A record exists only if a REAL, PASSED verification run backs it. `put_verified` refuses
    anything else -- "do NOT promote uncertain hypotheses into permanent knowledge"
    (ARCHITECTURE.md section 9). An unverified diagnosis is never consolidated, however
    confident the model was.
  * Corrections supersede; they never overwrite. A newer verified record for the same
    (topic, affected components) marks the old one `superseded` and points at its replacement.
  * Similarity is BRE's own (ADR-0001 declined chromadb + torch): binary-bag cosine over the
    incident's analysed keywords. Deterministic, dependency-free, explainable in a sentence.

Backed by the existing `engineering_memory` table (extended by `ensure_columns`).
"""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from apps.api.database import EngineeringMemoryDB, VerificationDB

MEMORY_TYPE = "verified_diagnosis"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def cosine(a: Iterable[str], b: Iterable[str]) -> float:
    """Binary-vector cosine: |A n B| / sqrt(|A||B|). 0 if either is empty."""
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / math.sqrt(len(sa) * len(sb))


@dataclass(frozen=True)
class MemoryEntry:
    id: str
    topic: str
    root_cause: str
    affected_components: tuple[str, ...]
    assumptions: tuple[str, ...]
    keywords: tuple[str, ...]
    source_incident_id: str
    source_predictor: str
    verification_run_id: str
    confidence: float
    status: str = "active"
    superseded_by: Optional[str] = None
    created_at: Optional[datetime] = field(default=None, compare=False)


def _to_entry(row: EngineeringMemoryDB) -> MemoryEntry:
    body = json.loads(row.content)
    return MemoryEntry(
        id=row.id, topic=row.topic or "general", root_cause=body["root_cause"],
        affected_components=tuple(body.get("affected_components", ())),
        assumptions=tuple(body.get("assumptions", ())),
        keywords=tuple(row.keywords or ()),
        source_incident_id=row.source_incident_id or "",
        source_predictor=body.get("source_predictor", ""),
        verification_run_id=row.verification_run_id or "",
        confidence=row.confidence or 0.0, status=row.status or "active",
        superseded_by=row.superseded_by, created_at=row.created_at,
    )


class MemoryNotVerified(ValueError):
    """Refused: the record is not backed by a real passed verification run."""


class MemoryStore:
    def __init__(self, db: Session) -> None:
        self.db = db

    def put_verified(
        self,
        *,
        topic: str,
        root_cause: str,
        affected_components: Iterable[str],
        assumptions: Iterable[str],
        keywords: Iterable[str],
        source_incident_id: str,
        source_predictor: str,
        verification_run_id: str,
        confidence: float,
    ) -> MemoryEntry:
        run = self.db.get(VerificationDB, verification_run_id)
        if run is None or run.status != "passed":
            raise MemoryNotVerified(
                f"verification run {verification_run_id!r} is "
                f"{'missing' if run is None else run.status}: only verified outcomes become memory"
            )
        if run.incident_id != source_incident_id:
            raise MemoryNotVerified("the verification run belongs to a different incident")

        components = tuple(sorted(affected_components))
        row = EngineeringMemoryDB(
            id=uuid.uuid4().hex[:12], type=MEMORY_TYPE, title=f"{topic}: {root_cause[:80]}",
            content=json.dumps({
                "root_cause": root_cause, "affected_components": list(components),
                "assumptions": list(assumptions), "source_predictor": source_predictor,
            }),
            source_incident_id=source_incident_id, confidence=float(confidence),
            topic=topic, keywords=sorted(set(keywords)), status="active",
            verification_run_id=verification_run_id, claim_class="B",
            created_at=_now(), updated_at=_now(),
        )
        # supersede, never overwrite: same (topic, components) -> the newer verified record wins
        for old in self.db.query(EngineeringMemoryDB).filter(
            EngineeringMemoryDB.type == MEMORY_TYPE, EngineeringMemoryDB.topic == topic,
            EngineeringMemoryDB.status == "active",
        ):
            if tuple(sorted(json.loads(old.content).get("affected_components", ()))) == components:
                old.status, old.superseded_by, old.updated_at = "superseded", row.id, _now()
        self.db.add(row)
        self.db.flush()
        return _to_entry(row)

    def active(self, topic: Optional[str] = None) -> list[MemoryEntry]:
        q = self.db.query(EngineeringMemoryDB).filter(
            EngineeringMemoryDB.type == MEMORY_TYPE, EngineeringMemoryDB.status == "active")
        if topic is not None:
            q = q.filter(EngineeringMemoryDB.topic == topic)
        return [_to_entry(r) for r in q.order_by(EngineeringMemoryDB.created_at)]

    def get(self, memory_id: str) -> Optional[MemoryEntry]:
        row = self.db.get(EngineeringMemoryDB, memory_id)
        return _to_entry(row) if row else None

    def all(self) -> list[MemoryEntry]:
        rows = self.db.query(EngineeringMemoryDB).filter(EngineeringMemoryDB.type == MEMORY_TYPE)
        return [_to_entry(r) for r in rows.order_by(EngineeringMemoryDB.created_at)]
