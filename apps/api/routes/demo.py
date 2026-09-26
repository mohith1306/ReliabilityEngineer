"""Demo workspace: build a throwaway target repository and an incident against it. BRE_DEMO=1 only.

A deployed instance has no repository of its own to break, so for the hackathon demo (and for a first
local trial) BRE can manufacture one: it copies a seeded fixture into a fresh git repository under
BRE_DEMO_DIR -- the only directory the demo allowlists -- and opens an incident against it. The
lifecycle that follows is the real one: real git checkpoint and branch, real pytest, real ledger.

Disabled unless BRE_DEMO=1, because it creates repositories on the server.
"""

from __future__ import annotations

import os
import shutil
import stat
import sys
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.api import settings
from apps.api.database import Base, IncidentDB, get_db
from reliability.evaluation.fixtures import build_fixture_repo
from reliability.evaluation.run import load_corpus

router = APIRouter()

CORPUS = "tests/e2e/corpus"
MARKER = ".bre-demo-workspace"  # BRE only ever deletes a directory it has itself marked

# what each scenario demonstrates, in the order a presenter would run them
SCENARIOS = {
    "seeded_failure": {
        "seed": "seed-001", "title": "Connection pool exhaustion (config regression)",
        "teaches": "The first time BRE sees this failure it does a full investigation. Once the fix is verified "
                   "it becomes memory, and the next similar incident is answered from it at zero Bob cost.",
    },
    "auth_timeout": {
        "seed": "seed-007", "title": "Login requests timing out (config regression)",
        "teaches": "A different component: ownership is learned per topic, so this starts cold.",
    },
    "connection_cap": {
        "seed": "seed-011", "title": "Connection pool exhaustion (LOOK-ALIKE: the cause is in code)",
        "teaches": "Same symptom, different cause. If memory answers, the test suite refutes it, the patch is "
                   "rolled back, the memory is excluded, and BRE re-investigates.",
    },
}


def _force_rmtree(path) -> None:
    """rmtree that survives git's read-only object files (Windows refuses to delete them otherwise, and
    `ignore_errors=True` would silently leave the directory behind)."""
    def fix(func, p, *_):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except OSError:
            pass

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=fix)
    else:  # pragma: no cover
        shutil.rmtree(path, onerror=fix)


class NewIncident(BaseModel):
    scenario: str


def _require_demo():
    if not settings.demo_enabled():
        raise HTTPException(status_code=404, detail="demo mode is off (set BRE_DEMO=1)")


@router.get("/scenarios")
def scenarios():
    _require_demo()
    return [{"scenario": k, **{f: v for f, v in s.items() if f != "seed"}} for k, s in SCENARIOS.items()]


@router.post("/incidents", status_code=201)
def new_incident(body: NewIncident, db: Session = Depends(get_db)):
    _require_demo()
    scenario = SCENARIOS.get(body.scenario)
    if scenario is None:
        raise HTTPException(status_code=400, detail=f"unknown scenario; choose from {sorted(SCENARIOS)}")
    spec = next(s for s in load_corpus(CORPUS) if s["id"] == scenario["seed"])

    root = settings.demo_dir()
    root.mkdir(parents=True, exist_ok=True)
    (root / MARKER).write_text("created by BRE demo mode; safe to delete\n", encoding="utf-8")
    repo = build_fixture_repo(spec["repo"], root / f"{spec['repo']}-{uuid.uuid4().hex[:8]}")
    meta = dict(spec["incident"].get("metadata", {}))
    meta.update({"repo_path": str(repo), "topic": spec["topic"], "demo_scenario": body.scenario})
    row = IncidentDB(
        id=uuid.uuid4().hex[:12], repository=spec["repo"], branch="main", type=spec["incident"]["type"],
        severity=spec["incident"].get("severity", "high"), status="DETECTED",
        description=spec["incident"]["description"], metadata_json=meta,
        created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    return {"id": row.id, "scenario": body.scenario, "title": scenario["title"]}


@router.post("/reset")
def reset(db: Session = Depends(get_db)):
    """Wipe every table and every demo repository. The presenter's 'start over' button."""
    _require_demo()
    bind = db.get_bind()   # the database THIS request is using, never a hard-wired one
    db.close()
    Base.metadata.drop_all(bind=bind)
    Base.metadata.create_all(bind=bind)
    root = settings.demo_dir()
    # A misconfigured BRE_DEMO_DIR must never let a reset wipe something real.
    if (root / MARKER).is_file():
        _force_rmtree(root)
    return {"reset": True}
