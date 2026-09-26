"""Per-(source, topic) standings -- computed from the outcome ledger, and from nothing else.

This is where Invariant 3 is enforced structurally rather than by convention. The table is built
by reading closed `OutcomeRecord`s, and only ones that satisfy ALL of:

  * status is `confirmed` or `refuted`                 (pending / abandoned move nothing)
  * the record is a DIAGNOSIS prediction               (a source's reputation is its diagnoses')
  * `verification_run_id` joins to a REAL `verification_runs` row
                                                       (excludes `eval:` harness closures and
                                                        anything a stray writer marked closed)
  * claim class is A or B                              (class C never moves reputation; and the
                                                        per-class weight comes from reputation.py)

Deliberately absent: commit counts, blame, anything from git history. Session 0008 measured that
git-derived ownership is indistinguishable from chance at small N, and that BRE's "agents" (Bob,
memory, analyzers) appear in no commit history at all. Ownership is learned here, from
verification, or not at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from apps.api.database import OutcomeRecordDB, VerificationDB
from asmos_bridge.ownership.reputation import reputation_update
from asmos_bridge.ownership.trust import ALPHA, BETA, ownership_score, trust
from models.outcome import PredictionType

# predictor ids as written by the engines -> the source name shown to humans
SOURCE_ALIASES = {"bob-adapter": "bob", "replay-bob": "bob", "bob-shell": "bob"}


def source_name(predictor_id: str) -> str:
    return SOURCE_ALIASES.get(predictor_id, predictor_id)


@dataclass(frozen=True)
class Standing:
    """One source's standing in one topic, with every component (Invariant 8)."""

    source: str
    topic: str
    verified_correct: float
    verified_total: float
    contribution_share: float
    trust: float
    ownership: float
    alpha: int = ALPHA
    beta: int = BETA

    def as_dict(self) -> dict:
        return {
            "source": self.source, "topic": self.topic,
            "verified_correct": self.verified_correct, "verified_total": self.verified_total,
            "contribution_share": round(self.contribution_share, 6),
            "trust": round(self.trust, 6), "ownership": round(self.ownership, 6),
            "alpha": self.alpha, "beta": self.beta,
        }


class OwnershipTable:
    def __init__(self, counts: dict[tuple[str, str], tuple[float, float]]) -> None:
        self._counts = counts

    # ── construction: the ONLY input is the ledger ────────────────────────────────────

    @classmethod
    def from_ledger(cls, db: Session, *, topics: Optional[Iterable[str]] = None) -> "OwnershipTable":
        q = (
            db.query(OutcomeRecordDB)
            .join(VerificationDB, OutcomeRecordDB.verification_run_id == VerificationDB.id)
            .filter(
                OutcomeRecordDB.prediction_type == PredictionType.DIAGNOSIS.value,
                OutcomeRecordDB.status.in_(("confirmed", "refuted")),
            )
        )
        if topics is not None:
            q = q.filter(OutcomeRecordDB.topic.in_(list(topics)))
        counts: dict[tuple[str, str], list[float]] = {}
        for rec in q:
            upd = reputation_update(rec.claim_class, rec.status)
            cell = counts.setdefault((source_name(rec.predictor_id), rec.topic), [0.0, 0.0])
            cell[0] += upd.verified_correct_delta
            cell[1] += upd.verified_total_delta
        return cls({k: (v[0], v[1]) for k, v in counts.items()})

    # ── reading ───────────────────────────────────────────────────────────────────────

    def standing(self, source: str, topic: str) -> Standing:
        vc, vt = self._counts.get((source, topic), (0.0, 0.0))
        total_correct = sum(c for (s, t), (c, _) in self._counts.items() if t == topic)
        share = (vc / total_correct) if total_correct > 0 else 0.0
        t = trust(vc, vt)
        return Standing(source, topic, vc, vt, share, t, ownership_score(t, share))

    def all(self) -> list[Standing]:
        return [self.standing(s, t) for (s, t) in sorted(self._counts)]
