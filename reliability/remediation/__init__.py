"""Remediation orchestration -- THE WRITE PATH. Stage S6.

The only package permitted to cause a change in a target repository, and only
behind a passed approval gate.

Contract:
    orchestrator.py RemediationOrchestrator.execute(incident, approval) -> Remediation

Preconditions, all enforced, none advisory:
    1. A matching approval row exists and is APPROVED.
    2. The target repository is on the allowlist.
    3. A git checkpoint exists for rollback (ARCHITECTURE.md section 25).
    4. Changes land on a working branch, never the default branch.

Constraints passed to Bob (ARCHITECTURE.md section 13): modify only necessary files,
no unrelated refactoring, never disable tests, never bypass safety checks.
"""
