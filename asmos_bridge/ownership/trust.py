"""Trust, ownership and routing math -- pure functions.

DERIVED FROM: ASMOS `src/asmos/ownership/trust.py` (specification_freeze_v1.0 sections 6, 8, 9).
These are ASMOS's equations, re-implemented (ADR-0001: vendored bridge, not a dependency) and
pinned to the reference by `tests/unit/test_asmos_parity.py` against vectors generated from the
real source by `scripts/gen_asmos_parity_vectors.py`. If this file drifts, that test fails.

Pure float-in / float-out: no state, no I/O. Inputs that belong to other subsystems arrive as
plain values (verified counts from the outcome ledger, similarity from the router, tau from the
tuning run).

Invariants:
    Inv 3  reputation moves only AFTER verification. These functions take *verified* counts only,
           never generation counts -- the only thing that can produce those counts is the outcome
           ledger, and only closures backed by a real verification run (see ledger.py).
    Inv 8  every computed score stores its components. `routing_decision` returns the audit
           fields, not a bare label.
"""

from __future__ import annotations

GLOBAL_SEARCH = "GLOBAL_SEARCH"
ROUTE = "ROUTE"

# ASMOS defaults: alpha+beta = prior strength 10, cold-start trust 0.70.
ALPHA = 7
BETA = 3


def trust(verified_correct: float, verified_total: float, alpha: float = ALPHA, beta: float = BETA) -> float:
    """Beta-prior trust:  (alpha + verified_correct) / (alpha + beta + verified_total).

    `verified_total` counts every verified observation (correct or not); `verified_correct` the
    correct subset, so 0 <= verified_correct <= verified_total. Counts may be fractional because
    class-B claims move reputation by half (reputation.py).

    Store `verified_total` beside the score: 0.70 at 2 observations is not the same evidence as
    0.70 at 200.
    """
    if verified_correct < 0 or verified_total < 0:
        raise ValueError("counts must be non-negative")
    if verified_correct > verified_total:
        raise ValueError("verified_correct cannot exceed verified_total")
    return (alpha + verified_correct) / (alpha + beta + verified_total)


def ownership_score(domain_expertise: float, contribution_share: float) -> float:
    """Per-topic ownership: 0.6 * DomainExpertise + 0.4 * ContributionShare.

    domain_expertise   Beta-prior trust restricted to the source's verified claims in this topic.
    contribution_share the source's verified-correct claims in T / all verified-correct claims in T.
    Both are products of verification, so Invariant 3 holds by construction.
    """
    return 0.6 * domain_expertise + 0.4 * contribution_share


def routing_score(sim_query_topic: float, ownership_score_v: float) -> float:
    """RoutingScore(a, q) = Sim(q, T) * Ownership(a, T).

    Topic relevance gated by who actually owns the topic: a perfectly on-topic query to a source
    with no ownership still scores 0.
    """
    return sim_query_topic * ownership_score_v


def routing_decision(scored_owners: list[tuple[str, float]], tau: float, k: int = 2) -> dict:
    """Similarity-gated routing with a global-search fallback.

    scored_owners  [(source_id, routing_score), ...] for candidate owners of the matched topic.
                   May be empty: no owner yet -> cold start -> GLOBAL_SEARCH.
    tau            fallback threshold. Best RoutingScore < tau means no confident owner, so fall
                   back to global search. That fallback is CORRECT on a cold start, not a failure.
    k              route to the top-k owners.

    Returns {"action": ROUTE|GLOBAL_SEARCH, "owners": [(source, score), ...], "top_score", "tau"}.
    """
    if not scored_owners:
        return {"action": GLOBAL_SEARCH, "owners": [], "top_score": None, "tau": tau}

    ranked = sorted(scored_owners, key=lambda pair: pair[1], reverse=True)
    top_score = ranked[0][1]

    if top_score < tau:
        return {"action": GLOBAL_SEARCH, "owners": [], "top_score": top_score, "tau": tau}

    return {"action": ROUTE, "owners": ranked[:k], "top_score": top_score, "tau": tau}
