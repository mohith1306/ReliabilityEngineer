"""Deterministic risk classification with a full factor breakdown.

Invariant 8: a risk level without its factor breakdown is unauditable. Every
RiskAssessment produced here carries `factors` = {score, thresholds, rules},
where rules maps each input to the points it contributed. No randomness, no
clock, no I/O -- the same inputs always classify to the same level, which is
S5 exit criterion 2.
"""

from __future__ import annotations

from typing import Any, Optional

from models.diagnosis import Diagnosis
from models.risk import RiskAssessment, RiskAssessmentCreate, RiskLevel

PREDICTOR_ID = "risk-classifier"

THRESHOLDS = {"CRITICAL": 7, "HIGH": 4, "MEDIUM": 2}


def _points_severity(value: str) -> int:
    return {"critical": 3, "high": 2, "medium": 1}.get(str(value).lower(), 0)


def _points_blast(value: int) -> int:
    if value >= 8:
        return 3
    if value >= 3:
        return 2
    if value >= 1:
        return 1
    return 0


def _points_tests(value: str) -> int:
    return {"none": 2, "partial": 1}.get(str(value).lower(), 0)


def score_to_level(score: int) -> RiskLevel:
    if score >= THRESHOLDS["CRITICAL"]:
        return RiskLevel.CRITICAL
    if score >= THRESHOLDS["HIGH"]:
        return RiskLevel.HIGH
    if score >= THRESHOLDS["MEDIUM"]:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


class RiskClassifier:
    def classify(
        self,
        diagnosis: Optional[Diagnosis | dict] = None,
        repo_context: Optional[dict] = None,
    ) -> RiskAssessment:
        context = dict(repo_context or {})
        diag = self._as_dict(diagnosis)

        severity = context.get("severity", "unknown")
        blast_radius = int(context.get("blast_radius", 0))
        migration = bool(context.get("database_migration", False))
        api_surface = bool(context.get("api_surface_affected", False))
        tests = str(context.get("tests_available", "none"))
        confidence = float(diag.get("confidence", 0.0)) if diag else 0.0

        rules = {
            "severity": {"input": str(severity), "points": _points_severity(severity)},
            "database_migration": {"input": migration, "points": 3 if migration else 0},
            "api_surface_affected": {"input": api_surface, "points": 2 if api_surface else 0},
            "blast_radius": {"input": blast_radius, "points": _points_blast(blast_radius)},
            "tests_available": {"input": tests, "points": _points_tests(tests)},
            "low_confidence": {"input": confidence, "points": 1 if confidence and confidence < 0.5 else 0},
        }
        score = sum(rule["points"] for rule in rules.values())
        level = score_to_level(score)
        factors = {
            "score": score,
            "thresholds": dict(THRESHOLDS),
            "rules": rules,
        }

        affected = list(diag.get("affected_components") or context.get("affected_components") or [])
        assessment_confidence = confidence if diag else 0.6

        return RiskAssessment(
            **RiskAssessmentCreate(
                incident_id=str(context.get("incident_id") or (diag.get("incident_id") if diag else "") or "unknown"),
                risk_level=level,
                confidence=max(0.0, min(1.0, assessment_confidence)),
                factors=factors,
                blast_radius=blast_radius,
                affected_components=[str(c) for c in affected],
                api_surface_affected=api_surface,
                database_migration=migration,
                tests_available=tests,
            ).model_dump(),
        )

    @staticmethod
    def _as_dict(diagnosis: Optional[Diagnosis | dict]) -> dict:
        if diagnosis is None:
            return {}
        if hasattr(diagnosis, "model_dump"):
            return diagnosis.model_dump()
        return dict(diagnosis)
