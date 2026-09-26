"""Verification -- the only thing that may close an outcome. Stage S7.

A remediation is not successful because code changed (ARCHITECTURE.md 4.3). It is
successful when the tests that were failing pass, the neighbourhood of the change still
passes, and nothing that used to pass now fails. Three levels, run in order, fail-fast, and
each recorded separately so a reader can see *which* level a patch died at:

    TARGETED    the exact tests that were red before the patch (measured, not claimed)
    COMPONENT   the whole test files those live in, plus tests for the modules that changed
    REGRESSION  the entire suite; passes iff nothing is newly red versus the baseline

Two refusals that matter as much as the checks:

  * No reproducing test -> the fix CANNOT be verified, and that is a failure, not a pass.
    An incident that never reproduced in the test suite must not close as "confirmed".
  * Zero tests collected is never a pass (`RunResult.ok` requires something to have run).

On PASS   every pending outcome for the incident closes `confirmed`, the incident RESOLVES,
          and the repo is returned to the branch it started on (the fix stays on its bre/*
          branch for a human to merge -- BRE never merges).
On FAIL   the patch is rolled back to the checkpoint, every pending outcome closes `refuted`,
          and the loop policy decides between another attempt and giving up. This is where
          reputation moves, and the only place it moves (ASMOS Invariant 3).
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Optional, Sequence

from sqlalchemy.orm import Session

from apps.api.database import RemediationDB, VerificationDB
from models.incident import IncidentStatus
from reliability.ledger.record import OutcomeLedger
from reliability.orchestration.lifecycle import Lifecycle
from reliability.remediation import git_ops
from reliability.verification.test_runner import RunResult, Scope, TestRunner

logger = logging.getLogger("bre.verification")

VERIFIER_ID = "verification-engine"
ENV_MAX_ATTEMPTS = "BRE_MAX_ATTEMPTS"
DEFAULT_MAX_ATTEMPTS = 3

_NODE_ID = re.compile(r"[\w./\\-]+\.py::\w+")


def max_attempts() -> int:
    """The hard cap on loop passes per incident (ERRATA A4). Never below 1."""
    try:
        return max(1, int(os.environ.get(ENV_MAX_ATTEMPTS, DEFAULT_MAX_ATTEMPTS)))
    except ValueError:
        return DEFAULT_MAX_ATTEMPTS


def extract_test_ids(*texts: Any) -> list[str]:
    """pytest node ids mentioned in evidence / metadata, forward-slashed and de-duplicated."""
    found: list[str] = []
    for text in texts:
        for match in _NODE_ID.findall(str(text or "")):
            node = match.replace("\\", "/")
            if node not in found:
                found.append(node)
    return found


@dataclass
class VerificationResult:
    verification: VerificationDB
    passed: bool
    reason: Optional[str]
    levels: dict[str, dict]
    fixed: list[str] = field(default_factory=list)
    regressions: list[str] = field(default_factory=list)
    next_state: IncidentStatus = IncidentStatus.RESOLVED


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _level(run: RunResult, selectors: Sequence[str], ok: bool, **extra) -> dict:
    s = run.summary()
    s.update({"ok": ok, "selectors": list(selectors), "failing": sorted(run.failing), **extra})
    return s


def _skipped(scope: Scope, why: str) -> dict:
    return {"scope": scope.value, "skipped": True, "ok": False, "reason": why}


class Verifier:
    def __init__(self, db: Session, *, runner: Optional[TestRunner] = None) -> None:
        self.db = db
        self.runner = runner or TestRunner()

    def verify(
        self,
        incident,                       # IncidentDB, status VERIFYING
        remediation: RemediationDB,     # status "completed", patch committed on its bre/* branch
        *,
        test_hints: Iterable[str] = (),
    ) -> VerificationResult:
        lifecycle = Lifecycle(self.db)
        if incident.status != IncidentStatus.VERIFYING.value:
            raise ValueError(f"incident {incident.id} is {incident.status}; verification runs only in VERIFYING")
        if remediation.status != "completed" or not remediation.commit_sha:
            raise ValueError(f"remediation {remediation.id} has no committed patch to verify")

        root = remediation.repo_root
        cp = git_ops.Checkpoint(
            root=root, base_branch=remediation.base_branch, base_sha=remediation.checkpoint_sha,
            branch=remediation.patch_reference, ref=f"refs/bre/checkpoints/{git_ops.slug(incident.id)}-attempt-{remediation.attempt}",
            preexisting_untracked=frozenset(remediation.preexisting_untracked or []),
        )
        git_ops.assert_on_bre_branch(root)

        baseline = set(remediation.baseline_failures or [])
        levels: dict[str, dict] = {}
        cases: list[dict] = []
        fixed: list[str] = []
        regressions: list[str] = []
        reason: Optional[str] = None

        # ---- TARGETED ---------------------------------------------------------------------
        hinted = [t for t in extract_test_ids(*test_hints) if t in baseline]
        targeted = sorted(hinted or baseline)
        if not targeted:
            reason = ("no reproducing test: nothing was failing before the patch, so there is nothing "
                      "to show the patch fixed -- an unverifiable fix is not a verified one")
            levels["targeted"] = _skipped(Scope.TARGETED, reason)
        else:
            run = self.runner.run(root, Scope.TARGETED, targeted)
            fixed = [t for t in targeted if t in run.passed]
            ok = run.ok and len(fixed) == len(targeted)
            levels["targeted"] = _level(run, targeted, ok, fixed=fixed)
            cases += _cases(run, Scope.TARGETED)
            if not ok:
                reason = f"targeted: {len(targeted) - len(fixed)} of {len(targeted)} previously failing test(s) still fail"

        # ---- COMPONENT --------------------------------------------------------------------
        if reason is None:
            files = self._component_files(root, targeted, remediation.changed_files or [])
            run = self.runner.run(root, Scope.COMPONENT, files)
            newly_red = run.failing - baseline
            still_red = run.failing & set(targeted)
            # A pre-existing red test that merely shares a file does not fail the component level;
            # a newly red one, or a targeted one that regressed back, does.
            ok = run.ran > 0 and not newly_red and not still_red and not run.timed_out
            levels["component"] = _level(run, files, ok, newly_failing=sorted(newly_red))
            cases += _cases(run, Scope.COMPONENT)
            if not ok:
                bad = sorted(newly_red | still_red)
                reason = f"component: {bad[:3] or 'no tests ran'} failed in {files}"
        else:
            levels["component"] = _skipped(Scope.COMPONENT, "an earlier level failed")

        # ---- REGRESSION -------------------------------------------------------------------
        if reason is None:
            run = self.runner.run(root, Scope.REGRESSION)
            regressions = sorted(run.failing - baseline)
            ok = run.ran > 0 and not regressions and not run.timed_out
            levels["regression"] = _level(run, [], ok, regressions=regressions,
                                          preexisting_failures=sorted(run.failing & baseline))
            cases += _cases(run, Scope.REGRESSION)
            if not ok:
                reason = (f"regression: {len(regressions)} test(s) newly failing: {regressions[:3]}"
                          if regressions else "regression: the suite did not run to completion")
        else:
            levels["regression"] = _skipped(Scope.REGRESSION, "an earlier level failed")

        passed = reason is None
        levels["verdict"] = {"passed": passed, "reason": reason}
        reg_level = levels["regression"]
        row = VerificationDB(
            id=uuid.uuid4().hex[:12],
            incident_id=incident.id,
            remediation_id=remediation.id,
            status="passed" if passed else "failed",
            tests_run=int(reg_level.get("ran") or levels.get("component", {}).get("ran") or 0),
            tests_passed=int(reg_level.get("passed") or levels.get("component", {}).get("passed") or 0),
            tests_failed=len(regressions) if not passed and regressions else
                         int(levels.get("targeted", {}).get("failed") or 0),
            regressions=regressions,
            test_results=cases,
            levels=levels,
            created_at=_now(),
            completed_at=_now(),
        )
        self.db.add(row)
        self.db.flush()

        # ---- consequences: the ONLY place outcomes close ----------------------------------------
        ledger = OutcomeLedger(self.db)
        closed = ledger.close_for_verification(incident.id, row.id, passed=passed, closed_by=VERIFIER_ID)
        lifecycle.record(
            incident.id, "verification", actor=VERIFIER_ID,
            detail={"passed": passed, "reason": reason, "verification_id": row.id,
                    "levels": {k: {"ok": v.get("ok"), "skipped": v.get("skipped", False)}
                               for k, v in levels.items() if k != "verdict"},
                    "outcomes_closed": {r.prediction_type.value: r.status.value for r in closed}},
        )

        if passed:
            next_state = IncidentStatus.RESOLVED
            lifecycle.transition(incident, next_state, actor=VERIFIER_ID,
                                 detail={"verification_id": row.id, "fixed": fixed})
            git_ops.release(cp)  # hand the user's checkout back; the fix stays on its bre/* branch
        else:
            git_ops.rollback(cp, keep_as=f"{git_ops.slug(incident.id)}-attempt-{remediation.attempt}")
            remediation.status = "rolled_back"
            remediation.rolled_back_at = _now()
            if (incident.attempt or 1) < max_attempts():
                lifecycle.bump_attempt(incident)
                next_state = IncidentStatus.REINVESTIGATING
            else:
                next_state = IncidentStatus.ABANDONED
            lifecycle.transition(incident, next_state, actor=VERIFIER_ID,
                                 detail={"reason": reason, "attempt": incident.attempt,
                                         "cap": max_attempts()})
        logger.info("verification %s for %s: %s", row.id, incident.id, "PASSED" if passed else reason)
        return VerificationResult(row, passed, reason, levels, fixed, regressions, next_state)

    # ── helpers ────────────────────────────────────────────────────────────────────────

    def _component_files(self, root: str, targeted: Sequence[str], changed: Sequence[str]) -> list[str]:
        """Whole test files: those the targeted tests live in, and tests named for changed modules."""
        files: list[str] = []
        for node in targeted:
            path = node.split("::", 1)[0]
            if path not in files:
                files.append(path)
        tracked = git_ops._paths(root, "ls-files", "-z")
        for changed_path in changed:
            stem = re.sub(r"\.[^.]+$", "", changed_path.rsplit("/", 1)[-1])
            for candidate in tracked:
                name = candidate.rsplit("/", 1)[-1]
                if name in (f"test_{stem}.py", f"{stem}_test.py") and candidate not in files:
                    files.append(candidate)
        return files


def _cases(run: RunResult, scope: Scope) -> list[dict]:
    return [{"name": c.name, "status": c.outcome, "level": scope.value, "error": c.message}
            for c in run.cases if c.outcome in ("passed", "failed", "error")]
