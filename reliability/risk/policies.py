"""Approval policy per risk level (ARCHITECTURE.md section 16 / ADR-0003).

    LOW      -> AUTO       nothing to ask a human
    MEDIUM   -> policy-dependent (safe default: HUMAN)
    HIGH     -> HUMAN      an approval row with verified identity
    CRITICAL -> HUMAN      an approval row with verified identity
"""

from __future__ import annotations

from enum import Enum

from models.risk import RiskLevel


class Requirement(str, Enum):
    AUTO = "AUTO"
    HUMAN = "HUMAN"


class ApprovalPolicy:
    def __init__(self, *, medium_requires_approval: bool = True):
        self.medium_requires_approval = medium_requires_approval

    def required_for(self, level: RiskLevel | str) -> Requirement:
        parsed = RiskLevel(level) if isinstance(level, str) else level
        if parsed is RiskLevel.LOW:
            return Requirement.AUTO
        if parsed is RiskLevel.MEDIUM:
            return (
                Requirement.HUMAN if self.medium_requires_approval else Requirement.AUTO
            )
        return Requirement.HUMAN
