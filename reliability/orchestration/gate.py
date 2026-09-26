"""The approval gate: HIGH/CRITICAL cannot reach REMEDIATING without an
approval row carrying verified operator identity (CLAUDE.md 5, ERRATA A6).

Deny-by-default: an incident with no risk assessment at all is treated as
CRITICAL -- unknown risk never auto-passes. The gate is consulted by the
transition entry point (POST /incidents/{id}/transition), so a direct status
request cannot walk around AWAITING_APPROVAL.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from models.incident import IncidentStatus
from reliability.risk.policies import ApprovalPolicy, Requirement

REMEDIATION_TARGET = IncidentStatus.REMEDIATING


class GateViolation(PermissionError):
    """A transition was refused by the approval gate."""


def latest_risk_level(db: Session, incident_id: str) -> Optional[str]:
    from apps.api.database import RiskAssessmentDB

    row = (
        db.query(RiskAssessmentDB)
        .filter(RiskAssessmentDB.incident_id == incident_id)
        .order_by(RiskAssessmentDB.created_at.desc())
        .first()
    )
    return row.risk_level if row else None


def _latest_assessment(db: Session, incident_id: str):
    from apps.api.database import RiskAssessmentDB

    return (
        db.query(RiskAssessmentDB)
        .filter(RiskAssessmentDB.incident_id == incident_id)
        .order_by(RiskAssessmentDB.created_at.desc())
        .first()
    )


def qualifying_approval(db: Session, incident_id: str, risk_level: str):
    """An APPROVED row with operator identity, recorded for this very risk
    level, and not older than the assessment it approves.

    Risk-level match matters: if there is no assessment the route stamps the
    approval `UNKNOWN`, which can never satisfy a levelled gate -- so the
    no-assessment path stays deny-by-default.
    """
    from apps.api.database import ApprovalDB

    assessment = _latest_assessment(db, incident_id)
    rows = (
        db.query(ApprovalDB)
        .filter(
            ApprovalDB.incident_id == incident_id,
            ApprovalDB.decision == "APPROVED",
            ApprovalDB.risk_level == risk_level,
            ApprovalDB.operator_id.isnot(None),
        )
        .order_by(ApprovalDB.created_at.desc())
        .all()
    )
    if assessment is None:
        return None
    fresh = [
        row for row in rows
        if row.created_at and assessment.created_at
        and row.created_at >= assessment.created_at
    ]
    return fresh[0] if fresh else None


def assert_can_enter(db: Session, incident_id: str, target: IncidentStatus | str) -> None:
    target = IncidentStatus(target) if isinstance(target, str) else target
    if target is not REMEDIATION_TARGET:
        return

    level = latest_risk_level(db, incident_id) or "CRITICAL"
    requirement = ApprovalPolicy().required_for(level)
    if requirement is Requirement.AUTO:
        return

    approval = qualifying_approval(db, incident_id, level)
    if approval is None:
        raise GateViolation(
            f"risk level {level} requires an approved approval row with verified "
            f"operator identity before entering REMEDIATING "
            f"(incident {incident_id}); none found or none current"
        )
