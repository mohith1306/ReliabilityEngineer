"""Risk classification and approval policy. Stage S5.

Runs BEFORE remediation, not after (ERRATA A2).

Contract:
    classifier.py   RiskClassifier.classify(diagnosis, repo_context) -> RiskAssessment
                    Returns a level AND its factor breakdown. A bare label is
                    unauditable and therefore unusable (Invariant 8).
    policies.py     ApprovalPolicy.required_for(risk) -> AUTO | HUMAN | MANDATORY_HUMAN
                    LOW auto; MEDIUM policy-dependent; HIGH and CRITICAL human.

Invariant: HIGH and CRITICAL cannot reach REMEDIATING without an approval row
carrying a verified identity. `approved_by` as free text is not an identity
(ERRATA A6).
"""
