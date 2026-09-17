"""Promote verified outcomes into durable engineering memory. Stage S8.

Derived from asmos/src/asmos/lifecycle/ and ARCHITECTURE.md section 9.

    learner.py  Consolidate(incident) -> MemoryRecord | None

Quality rule (ARCHITECTURE.md section 9): do NOT promote uncertain hypotheses into
permanent knowledge. The lifecycle is candidate -> verified outcome -> confidence
score -> memory. An unverified diagnosis is never consolidated, however confident
the model was.

Note: ASMOS's own forgetting/lifecycle logic exists but is OFF by default and not
wired to a continuous loop -- treat continuous forgetting as out of scope here too,
rather than inheriting an untested path.
"""
