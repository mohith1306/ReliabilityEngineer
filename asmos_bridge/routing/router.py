"""Route an incident to the diagnosis source most likely to be verifiably right.

DERIVED FROM: ASMOS `src/asmos/routing/router.py` (TransactiveRouter) -- the equations are
ASMOS's; the mapping onto BRE is described in docs/architecture/ASMOS_INTEGRATION.md.

The choice BRE makes per incident is between two ways of getting a diagnosis:

    memory        reuse a diagnosis that a passing test suite already vouched for. Free.
    GLOBAL_SEARCH a full investigation by IBM Bob. Expensive, and correct by construction.

    RoutingScore(memory, q) = Sim(q, best verified memory in T) * Ownership(memory, T)
        best score >= tau  -> ROUTE to memory
        best score <  tau  -> GLOBAL_SEARCH   (also: no memory in the topic at all)

Ownership(memory, T) = 0.6 * Trust + 0.4 * ContributionShare, both learned from verified reuse
outcomes in the ledger -- so a memory that keeps being right earns the right to answer less-
similar incidents, and one that gets refuted loses it, with no retraining and no threshold edit.
A cold start (no memory in the topic) falls back to Bob. That is correct behaviour, not a failure.

INVARIANT 8: the decision returns its components -- similarity, ownership (with its trust and
share), tau, the ranked candidates and the action -- not a bare label. The caller writes them to
the ledger as a `routing` prediction at decision time.

Scope honesty: this routes *sources*. It says nothing about ranking evidence within a route; that
is ordinary retrieval, and ASMOS's own README says ASMOS does not win at span retrieval.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from asmos_bridge.memory.store import MemoryEntry, MemoryStore, cosine
from asmos_bridge.ownership.ledger import OwnershipTable, Standing
from asmos_bridge.ownership.trust import GLOBAL_SEARCH, ROUTE, ownership_score, routing_decision, routing_score, trust

MEMORY_SOURCE = "memory"
BOB_SOURCE = "bob"
DEFAULT_TAU = 0.35  # ASMOS's stated default; used ONLY when no tuning artifact exists
ENV_TAU = "BRE_TAU"
ENV_TAU_FILE = "BRE_TAU_FILE"
TUNED_TAU_FILE = Path(__file__).resolve().parents[2] / "docs" / "artifacts" / "tau_tuning_latest.json"


def resolve_tau() -> tuple[float, str]:
    """(tau, where it came from). Tuned value if a stamped tuning artifact exists, never silently."""
    raw = os.environ.get(ENV_TAU)
    if raw:
        try:
            return float(raw), f"env:{ENV_TAU}"
        except ValueError:
            pass
    path = Path(os.environ[ENV_TAU_FILE]) if os.environ.get(ENV_TAU_FILE) else TUNED_TAU_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return float(data["tau"]), f"tuned:{data.get('artifact', path.name)}"
    except (OSError, ValueError, KeyError):
        return DEFAULT_TAU, "default:asmos"


@dataclass
class RoutingDecision:
    action: str                                  # ROUTE | GLOBAL_SEARCH
    routed_to: str                               # memory | bob
    topic: str
    tau: float
    tau_source: str
    top_score: Optional[float]
    reason: str
    memory: Optional[MemoryEntry] = None
    components: dict = field(default_factory=dict)


class TransactiveRouter:
    def __init__(self, db: Session, *, tau: Optional[float] = None, frozen_ownership: bool = False) -> None:
        self.db = db
        # ABLATION ONLY. With ownership frozen at its cold-start prior, verified outcomes stop moving
        # the score -- the single-variable ablation ASMOS itself uses to show that the benefit comes
        # from ownership EVOLUTION, not from the prior. Never enabled outside evaluation.
        self.frozen_ownership = frozen_ownership
        if tau is not None:
            self.tau, self.tau_source = tau, "explicit"
        else:
            self.tau, self.tau_source = resolve_tau()

    def route(self, *, topic: str, keywords: Iterable[str],
              exclude_memory_ids: Iterable[str] = ()) -> RoutingDecision:
        keywords = list(keywords)
        excluded = set(exclude_memory_ids)
        entries = [e for e in MemoryStore(self.db).active(topic) if e.id not in excluded]
        table = None if self.frozen_ownership else OwnershipTable.from_ledger(self.db)
        standing = (table.standing(MEMORY_SOURCE, topic) if table is not None
                    else Standing(MEMORY_SOURCE, topic, 0.0, 0.0, 0.0, trust(0, 0), ownership_score(trust(0, 0), 0.0)))

        base = {"topic": topic, "tau": self.tau, "tau_source": self.tau_source,
                "ownership": standing.as_dict(), "excluded_memory": sorted(excluded)}

        if not entries:
            why = ("cold start: no verified memory in this topic" if not excluded
                   else "every candidate memory was already tried on this incident and failed verification")
            return RoutingDecision(GLOBAL_SEARCH, BOB_SOURCE, topic, self.tau, self.tau_source, None, why,
                                   components={**base, "candidates": [], "action": GLOBAL_SEARCH, "reason": why})

        ranked = sorted(((cosine(keywords, e.keywords), e) for e in entries), key=lambda p: -p[0])
        sim, best = ranked[0]
        score = routing_score(sim, standing.ownership)
        decision = routing_decision([(MEMORY_SOURCE, score)], self.tau, k=1)
        candidates = [{"memory_id": e.id, "similarity": round(s, 4), "source_incident": e.source_incident_id}
                      for s, e in ranked[:3]]
        components = {**base, "similarity": round(sim, 6), "routing_score": round(score, 6),
                      "candidates": candidates, "best_memory_id": best.id, "action": decision["action"]}

        if decision["action"] == ROUTE:
            why = (f"similarity {sim:.2f} x ownership {standing.ownership:.2f} = {score:.2f} "
                   f">= tau {self.tau:.2f}")
            components["reason"] = why
            return RoutingDecision(ROUTE, MEMORY_SOURCE, topic, self.tau, self.tau_source, score, why,
                                   memory=best, components=components)
        why = (f"similarity {sim:.2f} x ownership {standing.ownership:.2f} = {score:.2f} "
               f"< tau {self.tau:.2f}: no confident owner, full investigation")
        components["reason"] = why
        return RoutingDecision(GLOBAL_SEARCH, BOB_SOURCE, topic, self.tau, self.tau_source, score, why,
                               components=components)
