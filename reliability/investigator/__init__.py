"""Evidence collection. Stage S2.

Builds an evidence package BEFORE any remediation is proposed (ARCHITECTURE.md 4.2).

Contract:
    analyzer.py     TaskAnalyzer.analyze(incident) -> IncidentTask
                    Classify the incident and name candidate components (topics).
    evidence.py     EvidenceCollector.collect(task) -> list[Evidence]
                    Pull from connectors; every item carries source_type,
                    source_reference, relevance and confidence.
    investigator.py Investigator.investigate(incident) -> Investigation
                    Orchestrates the above; writes evidence rows; never mutates
                    the target repository.

Invariant: this package is READ-ONLY with respect to the target repo.
"""
