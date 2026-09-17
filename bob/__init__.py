"""IBM Bob adapter -- the external engineering capability. Stage S4.

Bob is treated as a boundary, not a library (ARCHITECTURE.md section 16). BRE sends
task + relevant context + constraints + expected output + verification requirements;
Bob returns analysis, code changes, tests and an explanation.

    adapter.py    BobAdapter.investigate / .diagnose / .remediate / .verify
                  (ARCHITECTURE.md section 16 omits `diagnose` while section 10
                  assigns root-cause analysis to Bob -- ERRATA B. It belongs here.)
    prompts.py    Task framing and constraint injection.
    execution.py  Transport. UNVERIFIED -- see below.

BLOCKING UNKNOWN (thread 0001#7): the actual Bob integration mechanism has not been
confirmed by a working call. ARCHITECTURE.md section 16 defers it deliberately. Every
downstream stage assumes it exists. Confirm it with a real call before building on it.

Obligations:
    - Capture token usage and wall time on EVERY call, into the outcome ledger.
      Cost cannot be reconstructed after the fact (ERRATA A8).
    - Until stage S6, nothing in this package may write to a target repository.
"""
