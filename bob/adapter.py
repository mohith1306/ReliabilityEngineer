"""BobAdapter -- BRE's read-only boundary to IBM Bob (stage S4).

ARCHITECTURE.md section 16: BRE sends task + context + constraints + expected
output + verification requirements; Bob returns analysis. This stage covers
investigate() and diagnose() only. remediate()/verify() exist as explicit
stage-6 stubs that raise: until a passed approval gate exists (CLAUDE.md
non-negotiable 5), no path from this package may touch a target repository.

Every call opens a pending OutcomeRecord carrying its measured cost
(ERRATA A8 / thread 0004#7): tokens from the turn's usage, wall time
from this process.

The adapter is transport-agnostic (bob/transport.py): the documented Bob Shell
CLI when it is usable, the experimental agent-host WebSocket otherwise.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from models.diagnosis import Diagnosis, DiagnosisCreate

from .errors import BobError
from .execution import DEFAULT_TURN_TIMEOUT
from .prompts import diagnose_prompt, investigate_prompt, prompt_fingerprint
from .transport import (
    DEFAULT_PROVIDER,
    AgentHostTransport,
    Transport,
    select_transport,
)

PREDICTOR_ID = "bob-adapter"


class DiagnosisParseError(BobError):
    """Bob's reply did not contain a parseable Diagnosis JSON object."""


class BobAdapter:
    def __init__(
        self,
        db=None,
        *,
        address: Optional[str] = None,
        provider: str = DEFAULT_PROVIDER,
        topic: str = "general",
        turn_timeout: float = DEFAULT_TURN_TIMEOUT,
        transport: Optional[Transport] = None,
    ):
        self.db = db
        self.address = address
        self.provider = provider
        self.topic = topic
        self.turn_timeout = turn_timeout
        # An explicit address pins the agent-host transport with no I/O; otherwise the
        # transport is chosen lazily at first use, so constructing an adapter never
        # touches the network or the filesystem.
        if transport is None and address is not None:
            transport = AgentHostTransport(address, provider=provider, turn_timeout=turn_timeout)
        self.transport = transport

    def investigate(self, incident: Any, evidence: Iterable[Any], *, working_directory: Optional[str] = None,
                    attempt: int = 1, prior_attempts: Iterable[dict] = ()) -> Diagnosis:
        return self._run(incident, evidence, investigate_prompt, working_directory, attempt, prior_attempts)

    def diagnose(self, incident: Any, evidence: Iterable[Any], *, working_directory: Optional[str] = None,
                 attempt: int = 1, prior_attempts: Iterable[dict] = ()) -> Diagnosis:
        return self._run(incident, evidence, diagnose_prompt, working_directory, attempt, prior_attempts)

    def remediate(self, *args, **kwargs):
        raise NotImplementedError(
            "S6: no write path without a passed approval gate (CLAUDE.md 5)"
        )

    def verify(self, *args, **kwargs):
        raise NotImplementedError("S7: verification engine not built yet")

    def _resolve_transport(self) -> Transport:
        if self.transport is None:
            self.transport = select_transport(turn_timeout=self.turn_timeout)
        return self.transport

    def _run(self, incident, evidence, prompt_fn, working_directory, attempt=1, prior_attempts=()) -> Diagnosis:
        evidence = list(evidence)
        prompt = prompt_fn(incident, evidence, list(prior_attempts))
        transport = self._resolve_transport()
        outcome = transport.run(prompt, working_directory=working_directory)
        diagnosis = _parse_diagnosis(outcome.text, incident_id=_incident_id(incident))

        if self.db is not None:
            from reliability.ledger.record import open_diagnosis_prediction

            open_diagnosis_prediction(
                self.db,
                incident_id=_incident_id(incident),
                predictor_id=PREDICTOR_ID,
                topic=self.topic,
                root_cause=diagnosis.root_cause,
                confidence=diagnosis.confidence,
                components={
                    "provider": outcome.provider,
                    "transport": transport.name,
                    "simulated": bool(outcome.extra.get("simulated", False)),
                    "evidence_count": len(evidence),
                    "source_types": sorted({
                        str(_field(item, "source_type")) for item in evidence
                    }),
                    "prompt_sha256": prompt_fingerprint(prompt),
                    "turn_id": outcome.turn_id,
                },
                attempt_number=attempt,
                cost_tokens=outcome.tokens,
                cost_wall_ms=outcome.wall_ms,
            )
            self.db.commit()

        return diagnosis


def _field(item: Any, name: str, default: Any = "") -> Any:
    if hasattr(item, "model_dump"):
        item = item.model_dump()
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _incident_id(incident: Any) -> str:
    value = _field(incident, "incident_id") or _field(incident, "id")
    if not value:
        value = f"inc-{uuid.uuid4()}"
    return str(value)


def _parse_diagnosis(reply: str, *, incident_id: str) -> Diagnosis:
    text = reply.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise DiagnosisParseError(f"no JSON object in reply: {reply[:300]!r}")
        text = text[start:end + 1]
    try:
        payload = json.loads(text)
    except ValueError as exc:
        raise DiagnosisParseError(f"invalid JSON diagnosis: {exc}: {text[:300]}") from exc

    payload.setdefault("incident_id", incident_id)
    created = DiagnosisCreate(**payload)
    if not created.assumptions:
        created.assumptions = ["none stated by the diagnosing agent"]
    return Diagnosis(
        id=f"dx-{uuid.uuid4().hex[:12]}",
        created_at=datetime.now(timezone.utc),
        **created.model_dump(),
    )
