"""Data sources behind a registry, so the engine is not tied to one provider.

ARCHITECTURE.md section 17. MVP set:

    repository.py  List files, detect project type and structure.
    git.py         Commit history, blame, diffs for the investigator (GitPython).
    git_history.py Commit log -> ownership claim events + author identity resolution
                   (subprocess). Used by S8 / scripts/measure_asymmetry.py, not by the
                   investigator.
    tests.py       Discover tests; run a scope; return structured results.
    ci.py          Parse CI failure output into a structured failure record.

Later, behind the same registry: monitoring, issue tracker, deployment, cloud.
Resist adding them now -- ARCHITECTURE.md section 33 lists "dozens of connectors"
as an explicit anti-goal.

All connectors are READ-ONLY. The single write path lives in
reliability/remediation/ and is approval-gated.
"""
