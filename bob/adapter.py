"""BobAdapter -- BRE's read-only boundary to IBM Bob (stage S4).

ARCHITECTURE.md section 16: BRE sends task + context + constraints + expected
output + verification requirements; Bob returns analysis. This stage covers
investigate() and diagnose() only. remediate()/verify() exist as explicit
stage-6 stubs that raise: until a passed approval gate exists (CLAUDE.md
non-negotiable 5), no path from this package may touch a target repository.

Every call opens a pending OutcomeRecord carrying its measured cost
(ERRATA A8 / thread 0004#7): tokens from the host's turn usage, wall time
from this process.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from models.diagnosis import Diagnosis, DiagnosisCreate

from .execution import (
    DEFAULT_TURN_TIMEOUT,
    AgentHostClient,
    AgentHostAddress,
    BobError,
    BobTurnTimeout,
    chat_channel_for,
    discover_agent_host,
)
from .prompts import diagnose_prompt, investigate_prompt, prompt_fingerprint

PREDICTOR_ID = "bob-adapter"
DEFAULT_PROVIDER = "copilot"


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
    ):
        self.db = db
        self.address = address
        self.provider = provider
        self.topic = topic
        self.turn_timeout = turn_timeout

    def investigate(self, incident: Any, evidence: Iterable[Any], *, working_directory: Optional[str] = None) -> Diagnosis:
        return self._run(incident, evidence, investigate_prompt, working_directory)

    def diagnose(self, incident: Any, evidence: Iterable[Any], *, working_directory: Optional[str] = None) -> Diagnosis:
        return self._run(incident, evidence, diagnose_prompt, working_directory)

    def remediate(self, *args, **kwargs):
        raise NotImplementedError(
            "S6: no write path without a passed approval gate (CLAUDE.md 5)"
        )

    def verify(self, *args, **kwargs):
        raise NotImplementedError("S7: verification engine not built yet")

    def _run(self, incident, evidence, prompt_fn, working_directory) -> Diagnosis:
        evidence = list(evidence)
        prompt = prompt_fn(incident, evidence)
        address: AgentHostAddress = discover_agent_host(self.address)
        started = time.perf_counter()

        with AgentHostClient(address) as client:
            client.initialize()
            session_uri = f"{self.provider}:/{uuid.uuid4()}"
            client.create_session(
                session_uri,
                self.provider,
                working_directory=working_directory,
            )
            chat_uri = chat_channel_for(session_uri)
            client.create_chat(session_uri, chat_uri)
            client.subscribe(session_uri)

            turn_id = str(uuid.uuid4())
            message = {"text": prompt, "origin": {"kind": "user"}}
            client.dispatch_action(chat_uri, {
                "type": "chat/pendingMessageSet",
                "kind": "queued",
                "id": turn_id,
                "message": message,
            }, client_seq=1)
            client.dispatch_action(chat_uri, {
                "type": "chat/turnStarted",
                "turnId": turn_id,
                "message": message,
            }, client_seq=2)

            completion = client.wait_for_notification(
                _is_turn_completion,
                timeout=self.turn_timeout,
                label=f"turn {turn_id} completion",
            )
            client.unsubscribe(chat_uri)

        wall_ms = (time.perf_counter() - started) * 1000.0
        turn = _extract_turn(completion)
        usage = turn.get("usage") or {}
        tokens = int(usage.get("promptTokens", 0) or 0) + int(
            usage.get("completionTokens", 0) or 0
        )
        reply = _turn_text(turn)
        diagnosis = _parse_diagnosis(
            reply, incident_id=_incident_id(incident)
        )

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
                    "provider": self.provider,
                    "evidence_count": len(evidence),
                    "source_types": sorted({
                        str(_field(item, "source_type")) for item in evidence
                    }),
                    "prompt_sha256": prompt_fingerprint(prompt),
                    "turn_id": turn_id,
                },
                cost_tokens=tokens,
                cost_wall_ms=wall_ms,
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


def _is_turn_completion(msg: dict) -> bool:
    params = msg.get("params") or {}
    for found in _walk(params):
        if not isinstance(found, dict):
            continue
        status = str(found.get("status", "")).lower()
        if status in ("completed", "complete", "done") and (
            "usage" in found or "responseParts" in found
        ):
            return True
        if "usage" in found and ("responseParts" in found or "text" in found):
            return True
    action = params.get("action") or {}
    if action.get("type") == "chat/turnCancelled":
        raise BobTurnTimeout(f"turn cancelled by host: {action}")
    return False


def _walk(value: Any):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _extract_turn(msg: dict) -> dict:
    params = msg.get("params") or {}
    for found in _walk(params):
        if isinstance(found, dict) and (
            "usage" in found or "responseParts" in found
        ):
            if "text" not in found and "responseParts" not in found and "usage" not in found:
                continue
            return found
    snapshot = params.get("snapshot") or {}
    for found in _walk(snapshot):
        if isinstance(found, dict) and ("usage" in found or "responseParts" in found):
            return found
    return params


def _turn_text(turn: dict) -> str:
    if isinstance(turn.get("text"), str):
        return turn["text"]
    parts = turn.get("responseParts") or []
    chunks = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        for key in ("text", "content", "value"):
            if isinstance(part.get(key), str):
                chunks.append(part[key])
                break
    return "\n".join(chunks)


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
