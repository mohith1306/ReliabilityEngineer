"""Engineering memory records, shaped to the ASMOS memory contract.

Derived from asmos/CONTRACT.md v1.2 and asmos/src/asmos/memory/checkpoint.py.

    checkpoint.py  The memory record. Field origins are enforced:
                     SYS -- set by the system, never accepted from agent output
                     LLM -- the only fields accepted from an agent
                     CMP -- computed downstream; always empty at creation
                   Carries verification status, claim class, evidence with internal
                   vs external references, component-wise confidence/utility, and
                   supersedes / superseded_by for corrections.
    store.py       Put / get / search. Similarity backend is BRE's own (ADR-0001
                   declines the chromadb + torch dependency).

Corrections supersede; they never overwrite. Same rule the session ledger follows.
"""
