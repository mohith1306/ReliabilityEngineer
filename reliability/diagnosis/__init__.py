"""Root-cause analysis. Stage S4.

BRE does not reason about the code itself -- it hands Bob a structured evidence set
and shapes what comes back (ARCHITECTURE.md section 10).

Contract:
    root_cause.py   RootCauseAnalyzer.analyze(investigation) -> Diagnosis
                    Must populate root_cause, evidence_ids, affected_components,
                    confidence, assumptions, unresolved_uncertainty. A diagnosis
                    with no assumptions listed is under-specified, not confident.
    confidence.py   Confidence calibration and its component breakdown (Invariant 8).

Obligation: every diagnosis writes a pending OutcomeRecord at creation time
(ADR-0003). Producing it changes no reputation -- only verification does.
"""
