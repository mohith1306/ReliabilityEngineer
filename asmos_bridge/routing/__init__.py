"""Route an incident to the diagnosis source most likely to be verifiably right.

Derived from asmos/src/asmos/routing/router.py.

    router.py    TransactiveRouter.route(incident_task) -> RoutingDecision
                 tau-gated: best RoutingScore below tau means no confident owner,
                 so fall back to full investigation. That fallback is CORRECT
                 behaviour on cold start, not a failure.
    tuning.py    tune_tau(queries) -- derived from the score distribution of real
                 incidents, never hardcoded. tau is embedder-specific; ASMOS's
                 frozen value is 0.351492 for all-MiniLM-L6-v2.

INVARIANT 8: RoutingDecision records its components -- per-topic similarity,
per-source ownership, tau, action, and the ranked candidates -- not a bare label.

Scope honesty: this routes *sources*. Ranking evidence candidates within a route is
an ordinary retrieval problem and is NOT an ASMOS claim -- ASMOS's own README states
it does not beat RAG at span retrieval. Keep the two separable when reporting results.
"""
