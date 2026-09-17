"""IBM Bob adapter -- the external engineering capability. Stage S4.

Bob is treated as a boundary, not a library (ARCHITECTURE.md section 16). BRE sends
task + relevant context + constraints + expected output + verification requirements;
Bob returns analysis, code changes and an explanation.

INTERFACE CONFIRMED (session 0003). ARCHITECTURE.md section 16 deferred this and every
stage from S4 onward assumed it. It is now documented rather than assumed:

    Bob Shell, non-interactive:  bob run --format json --mode ask|plan|agent
    Auth:                        BOB_API_KEY (scope: Inference)
    Docs:                        https://bob.ibm.com/docs/shell

    adapter.py   BobAdapter.investigate / .diagnose / .plan_remediation / .remediate
                 plus preflight(), which reports availability without a billable call.

Three things the interface gives BRE for free, each closing an ERRATA item:

    ask | plan | agent      A native read/write boundary. ask and plan cannot modify
                            the workspace, so stages S2-S5 are structurally read-only
                            rather than read-only by convention.
    --max-turns/--max-cost  Native termination bounds for the reinvestigation loop
                            (ERRATA A4), enforced by Bob rather than simulated by us.
    stats.total_tokens      Per-call token, duration and cost accounting (ERRATA A8),
    stats.duration_ms       reported by Bob rather than instrumented around it.

One thing it does NOT give us: the JSON result carries no list of changed files. So
Remediation.changed_files must be derived from git, not from Bob's output. Git is the
better source anyway -- it records what actually changed rather than what Bob believes
it changed.

STILL OPEN (thread 0001#7): no live round trip has been made. Bob Shell is not
installed here and BOB_API_KEY is not set. The adapter is written against the
documented contract and unit-tested against the documented schema, but the contract
has not been confirmed against a running Bob. Close it with:

    venv/Scripts/python.exe scripts/verify_bob.py

Obligations:
    - Every call records tokens and wall time into the outcome ledger. Cost cannot be
      reconstructed after the fact.
    - remediate() refuses unless allow_writes=True. Until S6 lands the approval gate,
      no caller in this repo is authorised to pass it.
"""
