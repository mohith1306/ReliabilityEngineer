"""Verification -- the only thing that may close an outcome. Stage S7.

A remediation is not successful because code changed (ARCHITECTURE.md 4.3).

Contract:
    test_runner.py  TestRunner.run(scope) -> TestResults
                    Scopes: TARGETED | COMPONENT | REGRESSION | FULL.
    verifier.py     Verifier.verify(remediation) -> Verification
                    On pass  -> close outcomes confirmed, incident RESOLVED.
                    On fail  -> close outcomes refuted, incident REINVESTIGATING.

Invariant: this package holds the sole write path to OutcomeRecord terminal states
(ADR-0003). Nothing else may mark a prediction confirmed or refuted.

Invariant: the reinvestigation loop carries an attempt counter with a hard cap and
an ABANDONED terminal outcome. An autonomous loop that cannot stop is a defect
(ERRATA A4).
"""
