"""The failure signature: what makes two incidents "the same failure".

Two reports of one failure are worded differently ("CI job failed on main: connection pool
exhausted" vs "DatabaseConnector test failed: connection pool exhaustion"), so the free-text
description alone is a poor similarity basis. What recurs across reports of the same failure is
what the *evidence* says: the failing test's id and the error text.

    signature = keywords(description + error text)
              + tokens of every failing pytest node id found in the CI / test evidence
                (`tests/test_dbpool.py::test_pool_sized_from_config` -> tests, dbpool, pool, sized, config, ...)

It is a set of tokens; similarity between two signatures is the cosine in `memory.store`. It cannot
tell apart two incidents that fail the SAME test for DIFFERENT reasons -- a look-alike -- and does not
pretend to. That is what verification and the trust update are for.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from reliability.investigator.analyzer import TaskAnalyzer
from reliability.verification.verifier import extract_test_ids

_SPLIT = re.compile(r"[^A-Za-z0-9]+")


def _tokens(node_id: str) -> list[str]:
    out = []
    for part in _SPLIT.split(node_id.replace("::", " ").replace(".py", " ")):
        p = part.lower()
        if len(p) >= 3 and p not in ("tests", "test") and not p.isdigit():
            out.append(p)
    return out


def failure_signature(incident: Any, evidence: Iterable[dict] = ()) -> list[str]:
    """`incident` needs .id/.type/.description/.metadata (an IncidentDB row via `to_model`, or a model)."""
    words = set(TaskAnalyzer().analyze(incident).keywords)
    texts = []
    for e in evidence:
        if e.get("source_type") in ("ci", "test"):
            texts.append(f"{e.get('source_reference', '')} {e.get('content', '')}")
    for node in extract_test_ids(*texts, getattr(incident, "description", ""), getattr(incident, "metadata", {})):
        words.update(_tokens(node))
    return sorted(words)
