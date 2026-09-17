---
session: 0002
title: Environment verified
author: "@dee (with Claude Opus 5)"
stage: S1
started: 2026-09-17T11:05:00Z
ended: 2026-09-17T11:40:00Z
status: closed
---

## Context on entry

Read session 0001 close-out and `docs/stages/STAGES.md`. Inherited three open threads:
#7 (Bob interface unverified), #8 (ownership asymmetry unmeasured), #10 (nothing
runtime-verified). This session targets #10 only — the cheapest of the three, and the one
gating the credibility of everything written in 0001.

Belief on entry: creating a venv and installing requirements would be routine. It was not.

## Entries

### 1. The default `python` on this machine cannot install packages
- **Type:** finding
- **What:** A bare `python` resolves to the msys2/ucrt64 build (3.11.7). It creates a
  POSIX-layout venv (`bin/`, not `Scripts/`), and every pip download fails TLS verification:
  `SSLCertVerificationError: ... terminated in a root certificate which is not trusted`.
  It has no trusted root CA store.
- **Why:** This costs a newcomer an afternoon and looks like a network or proxy problem
  rather than a Python-selection problem. It is the first thing that will bite a teammate.
- **Evidence:** `python -c "import sys; print(sys.executable)"` returns
  `C:/msys64/ucrt64/bin/python.exe`; `pip install -r requirements.txt` fails on every
  package with SSLCertVerificationError.
- **Status:** resolved

### 2. Rebuilt the venv on CPython 3.13.7
- **Type:** change
- **What:** Deleted the msys2 venv, rebuilt with
  `C:/Users/csdee/AppData/Local/Programs/Python/Python313/python.exe`. Standard
  `Scripts/` layout, working SSL, all 10 requirements installed cleanly.
- **Why:** That interpreter is the one the ASMOS project already uses successfully, so it
  is the known-good choice on this machine rather than a guess.
- **Evidence:** `ASMOS/.venv/pyvenv.cfg` names Python313 as its base; install completed
  with fastapi 0.141.1, pydantic 2.13.5, sqlalchemy 2.0.54, pytest 9.1.1.
- **Status:** resolved

### 3. README venv instructions were wrong and are now corrected
- **Type:** change
- **What:** The instructions written in 0001 said `python -m venv venv` then
  `venv\Scripts\activate`. Both halves are wrong on this machine — the wrong interpreter,
  and the wrong layout for the interpreter that command actually selects.
- **Why:** Session 0001 wrote setup instructions without running them. Exactly the failure
  mode the evidence rule exists to catch, and it was caught on the next session because
  #10 was logged rather than glossed.
- **Evidence:** `README.md` "Running it" section now names the CPython path explicitly and
  explains the msys2 failure mode.
- **Status:** resolved

### 4. Unit suite passes — thread 0001#10 closed
- **Type:** verification
- **What:** `pytest tests/unit -q` → **11 passed in 0.50s**. All eleven outcome-ledger
  invariants from ADR-0003 hold: pending never moves reputation, class C never moves
  reputation even when verified, refutation does move it, non-terminal close rejected,
  double-close rejected, cost and tenant fields present from creation.
- **Why:** These were written in 0001 as intent with no observed pass. They are now evidence.
- **Evidence:** `venv/Scripts/python.exe -m pytest tests/unit -q` → `11 passed in 0.50s`.
- **Status:** resolved — closes thread 0001#10

### 5. Phase 1 API verified end to end
- **Type:** verification
- **What:** Added `tests/integration/test_api_smoke.py`. Confirms health, incident CRUD,
  repository filtering, 404 on missing, the full nine-state happy path, rejection of an
  illegal transition, `CLOSED` as terminal, rejection of an unknown status string, and the
  investigation + evidence + complete round trip.
- **Why:** S1 was marked DONE in 0001 on the strength of the code existing, not of it
  running. It now runs.
- **Evidence:** `venv/Scripts/python.exe -m pytest` → **20 passed, 3 xfailed in 3.90s**.
- **Status:** resolved

### 6. Three ERRATA gaps confirmed real, and pinned
- **Type:** verification
- **What:** Wrote the three known integrity gaps as `xfail(strict=True)` tests rather than
  prose. All three fail exactly as documented: an investigation can be created against a
  nonexistent `incident_id`; `started_at` is never populated; a `DETECTED` incident cannot
  be closed as a false alarm.
- **Why:** `strict=True` means the suite goes red the day someone fixes one of these without
  updating ERRATA. A documented gap that nothing enforces rots into a wrong document.
- **Evidence:** 3 xfailed, 0 xpassed. See `tests/integration/test_api_smoke.py` final block.
- **Status:** resolved — the gaps themselves remain open work for S2

### 7. Both documented deprecations reproduce on 3.13
- **Type:** verification
- **What:** `@app.on_event("startup")` and `datetime.utcnow()` both emit DeprecationWarning
  under Python 3.13.7 — 55 warnings across the suite before filtering.
- **Why:** ERRATA section B listed both from reading. They are now observed, so the entries
  are evidence rather than inference.
- **Evidence:** `apps/api/main.py:15`, `models/incident.py:69`,
  `apps/api/routes/incidents.py:69`, `apps/api/routes/investigations.py:16,57,72`.
- **Status:** open — warnings are filtered in `pytest.ini` for readability, with a comment
  saying to delete the filters once fixed. Not fixed in this session.

### 8. pytest.ini added
- **Type:** change
- **What:** `testpaths`, `pythonpath = .`, `--strict-markers`, and two narrowly scoped
  warning filters that name the ERRATA items they suppress.
- **Why:** `pythonpath = .` is what lets the suite import `models` and `apps` without an
  editable install. `--strict-markers` stops a typo'd marker silently doing nothing.
- **Evidence:** `pytest.ini`; suite runs from the repo root with no PYTHONPATH set.
- **Status:** resolved

## Close-out

- **Shipped:** Working venv on CPython 3.13.7 with all dependencies. Full suite green —
  **20 passed, 3 xfailed**. Phase 1 verified rather than assumed. Three ERRATA gaps and two
  deprecations converted from inference to observation. Corrected setup instructions that
  session 0001 got wrong. `pytest.ini`.
- **Open threads:** #7 Bob interface unverified (blocking S4, unassigned) · #8 ownership
  asymmetry unmeasured (blocking the S8 premise, unassigned) · 0002#7 deprecations
  reproduce but are not fixed (cosmetic, unassigned)
- **Next session should:** close thread #7 — one round-trip call to IBM Bob from a script,
  capturing tokens and latency. It is the largest schedule risk in the project and nothing
  from S4 onward can be planned honestly until it is answered.
- **Stage delta:** S1 DONE (now evidence-backed rather than assumed); S2 remains NOT_STARTED
