"""Workflow driver over the incident state machine.

Contract:
    workflow.py  Drives DETECTED -> ... -> CLOSED, emitting the domain events of
                 ARCHITECTURE.md section 22 and enforcing legal transitions from
                 models/incident.py.

Known gap (ERRATA A5): the transition table has no failure or abort paths, no
DETECTED -> CLOSED edge for false alarms, and no rollback state, while the
sub-status enums already define FAILED and ROLLED_BACK. Fix the table before
building on it.
"""
