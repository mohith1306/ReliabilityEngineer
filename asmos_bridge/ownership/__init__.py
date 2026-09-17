"""Learned per-(source, topic) ownership from verified outcomes. Stage S8.

Derived from asmos/src/asmos/ownership/.

    trust.py        Beta-prior trust, ownership score, routing score. Pure functions.
                      Trust(a,T)     = (alpha + verified_correct) / (alpha + beta + verified_total)
                                       alpha=7, beta=3 -> cold start 0.70
                      Ownership(a,T) = 0.6*Trust + 0.4*ContributionShare
                      RoutingScore   = Sim(q,T) * Ownership(a,T)
    reputation.py   Claim-class-gated updates.
                      A (reproduced failure) verified -> full,  refuted -> full negative
                      B (inferred cause)     verified -> half,  refuted -> half negative
                      C (speculation)        never moves reputation
    ledger.py       Per-(source, topic) verified counts, fed ONLY by the outcome ledger.

INVARIANT 3, structurally enforced: reputation moves only on a verification outcome,
never on generation. The only permitted input is reliability.ledger closing a record.
If anything here can be called from a diagnosis path, that is a bug.
"""
