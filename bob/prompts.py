"""Task framing and constraint injection for Bob calls (ARCHITECTURE.md section 16).

Every prompt Bob receives carries: task, relevant context, constraints, expected
output, verification requirements. The output contract is a JSON Diagnosis so
the reply can be validated against models/diagnosis.py instead of trusted.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Optional

CONSTRAINTS = """\
CONSTRAINTS (binding):
- READ-ONLY: do not modify, create, or delete any file; do not run git write commands.
- Base the diagnosis only on the evidence below plus read-only inspection if your
  tools allow it. If the evidence is insufficient, lower your confidence and say so
  in unresolved_uncertainty.
- A diagnosis with no assumptions listed is under-specified. List yours."""

OUTPUT_CONTRACT = """\
EXPECTED OUTPUT: reply with ONLY one JSON object, no prose outside it:
{
  "root_cause": "<one paragraph, specific>",
  "confidence": <0.0-1.0>,
  "affected_components": ["<file or module>", ...],
  "evidence_ids": ["<source_reference>", ...],
  "assumptions": ["...", ...],
  "unresolved_uncertainty": ["...", ...]
}"""

VERIFICATION_REQUIREMENTS = """\
VERIFICATION REQUIREMENTS:
Your diagnosis is a prediction. It will be written to the outcome ledger as
pending and closed only when a verification run confirms or refutes it. Cite
evidence_ids you actually used; uncited claims count against you."""


def _dump(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return value
    return json.dumps(value, indent=2, default=str)


def evidence_block(evidence: Iterable[Any]) -> str:
    lines = []
    for item in evidence:
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        lines.append(
            f"- [{item.get('source_type')}] {item.get('source_reference')} "
            f"(relevance={item.get('relevance_score', 0.0):.2f}, "
            f"confidence={item.get('confidence', 0.0):.2f}): "
            f"{str(item.get('content', ''))[:500]}"
        )
    return "\n".join(lines) if lines else "(no evidence collected)"


def investigate_prompt(incident: Any, evidence: Iterable[Any]) -> str:
    return (
        "TASK: diagnose the root cause of this incident from the evidence.\n\n"
        f"INCIDENT:\n{_dump(incident)}\n\n"
        f"EVIDENCE:\n{evidence_block(evidence)}\n\n"
        f"{CONSTRAINTS}\n\n{OUTPUT_CONTRACT}\n\n{VERIFICATION_REQUIREMENTS}"
    )


def diagnose_prompt(incident: Any, evidence: Iterable[Any]) -> str:
    return investigate_prompt(incident, evidence)


def prompt_fingerprint(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()[:16]
