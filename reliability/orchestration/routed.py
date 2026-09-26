"""The routed diagnosis source: ask verified memory when it has earned the right, else Bob.

Wires `TransactiveRouter` into the loop as a drop-in `diagnoser`. For each incident it:

  1. asks the router: reuse a verified memory, or fall back to a full investigation?
  2. opens a `routing` prediction in the ledger AT DECISION TIME with every component
     (Invariant 8) -- it is closed later by whether the routed answer verified;
  3. on ROUTE, builds the diagnosis from the memory record (0 Bob tokens) and opens a diagnosis
     prediction under the source `memory`, so verification can move MEMORY's reputation;
  4. on GLOBAL_SEARCH, calls Bob exactly as before.

Nothing here moves reputation (Invariant 3): both predictions open `pending`. Only the verifier,
later, closes them, and the ownership table reads those closures.

A memory that already failed verification on THIS incident is excluded from the next attempt, so
a re-investigation cannot be routed straight back to the answer that just lost.
"""

from __future__ import annotations

import uuid
from typing import Callable

from apps.api.database import OutcomeRecordDB
from asmos_bridge.consolidation.learner import incident_keywords
from asmos_bridge.ownership.trust import ROUTE
from asmos_bridge.routing.router import BOB_SOURCE, MEMORY_SOURCE, TransactiveRouter
from models.diagnosis import Diagnosis
from models.outcome import PredictionType
from reliability.ledger.record import open_diagnosis_prediction, open_routing_prediction
from reliability.orchestration.loop import DiagnoseRequest, DiagnoseResult, bob_diagnoser

ROUTER_ID = "asmos-router"


def _tried_memories(req: DiagnoseRequest) -> list[str]:
    rows = (
        req.db.query(OutcomeRecordDB)
        .filter(OutcomeRecordDB.incident_id == req.incident.id,
                OutcomeRecordDB.predictor_id == MEMORY_SOURCE,
                OutcomeRecordDB.prediction_type == PredictionType.DIAGNOSIS.value)
        .all()
    )
    return [r.components.get("memory_id") for r in rows if r.components.get("memory_id")]


def make_routed_diagnoser(fallback: Callable[[DiagnoseRequest], DiagnoseResult] = bob_diagnoser,
                          *, frozen_ownership: bool = False):
    def routed_diagnoser(req: DiagnoseRequest) -> DiagnoseResult:
        router = TransactiveRouter(req.db, frozen_ownership=frozen_ownership)
        decision = router.route(
            topic=req.topic, keywords=incident_keywords(req.incident, req.evidence),
            exclude_memory_ids=_tried_memories(req),
        )
        open_routing_prediction(
            req.db, incident_id=req.incident.id, predictor_id=ROUTER_ID, topic=req.topic,
            routed_to=decision.routed_to, confidence=min(1.0, max(0.0, decision.top_score or 0.0)),
            components=decision.components, attempt_number=req.attempt,
        )
        meta = {"routing": {"action": decision.action, "routed_to": decision.routed_to,
                            "reason": decision.reason, "tau": decision.tau, "tau_source": decision.tau_source,
                            "score": decision.top_score}}

        if decision.action != ROUTE or decision.memory is None:
            result = fallback(req)
            result.meta = {**result.meta, **meta}
            return result

        m = decision.memory
        sim = decision.components["similarity"]
        confidence = round(min(0.95, m.confidence * sim), 4)
        diagnosis = Diagnosis(
            id=f"dx-{uuid.uuid4().hex[:12]}", incident_id=req.incident.id, root_cause=m.root_cause,
            confidence=confidence, affected_components=list(m.affected_components),
            evidence_ids=[], assumptions=list(m.assumptions) + [
                f"reused from verified incident {m.source_incident_id} (similarity {sim:.2f}); "
                "this incident may differ in a way the keywords do not capture"],
            unresolved_uncertainty=["memory reuse is only as good as the similarity of the two incidents"],
        )
        open_diagnosis_prediction(
            req.db, incident_id=req.incident.id, predictor_id=MEMORY_SOURCE, topic=req.topic,
            root_cause=diagnosis.root_cause, confidence=confidence,
            components={"memory_id": m.id, "source_incident": m.source_incident_id,
                        "similarity": sim, "ownership": decision.components["ownership"],
                        "routing_score": decision.top_score, "tau": decision.tau, "simulated": False},
            attempt_number=req.attempt, cost_tokens=0, cost_wall_ms=0.0,
        )
        req.db.commit()
        return DiagnoseResult(diagnosis, MEMORY_SOURCE, meta)

    return routed_diagnoser


routed_diagnoser = make_routed_diagnoser()
