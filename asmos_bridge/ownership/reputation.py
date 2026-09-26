"""Claim-class-gated reputation updates.

DERIVED FROM: ASMOS `src/asmos/ownership/reputation.py` (frozen specification).

    class A  (objective: a reproduced failure)   verified -> full update    refuted -> full negative
    class B  (derived: an inferred cause)        verified -> half update    refuted -> half negative
    class C  (subjective: speculation)           NEVER moves reputation

An "update" is a pair of deltas to (verified_correct, verified_total). A refutation adds to the
total but not to the correct count, so it lowers trust; a verification adds to both.

INVARIANT 3, structurally: the only statuses that produce a non-zero update are the two
verification outcomes. `pending` and `abandoned` are not in the table, so producing a diagnosis
-- or losing one to the attempt cap -- moves nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

FULL_UPDATE = 1.0
HALF_UPDATE = 0.5
NO_UPDATE = 0.0

# BRE's ledger says confirmed/refuted; ASMOS says verified/refuted. Same two events.
_VERIFIED = {"verified", "confirmed"}
_REFUTED = {"refuted"}


@dataclass(frozen=True)
class ReputationUpdate:
    verified_correct_delta: float
    verified_total_delta: float


def reputation_update(claim_class: str, verification_status: str) -> ReputationUpdate:
    claim_class = claim_class.upper()
    status = verification_status.lower()

    if claim_class == "C":
        return ReputationUpdate(NO_UPDATE, NO_UPDATE)

    weight = {"A": FULL_UPDATE, "B": HALF_UPDATE}.get(claim_class)
    if weight is None:
        return ReputationUpdate(NO_UPDATE, NO_UPDATE)

    if status in _VERIFIED:
        return ReputationUpdate(weight, weight)
    if status in _REFUTED:
        return ReputationUpdate(NO_UPDATE, weight)
    return ReputationUpdate(NO_UPDATE, NO_UPDATE)  # pending, abandoned, anything else
