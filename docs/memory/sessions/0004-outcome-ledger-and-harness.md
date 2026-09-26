---
session: 0004
title: Outcome ledger and evaluation harness
author: opencode (mimo)
stage: S3
started: 2026-09-26T17:00:00Z
ended: 2026-09-26T17:40:00Z
status: closed
---

## Context on entry

Catch-up read: STAGES.md, INDEX.md (0001-0003), ADR-0003 (the decision this
stage implements), `models/outcome.py` and its 11 unit tests (both pre-existing
from session 0001), and the ledger contract in `reliability/ledger/__init__.py`.
S2 was DONE (session 0003). S3 was NOT_STARTED with no blockers.

## Entries

### 1. Ledger persistence mirrors the Pydantic model, with guards at the write path
- **Type:** change
- **What:** `OutcomeRecordDB` table in `apps/api/database.py`; `OutcomeLedger` in
  `reliability/ledger/record.py` with `open` / `close` / `close_for_verification`
  / `abandon_pending` / `pending_for_incident`. Three guards sit in `open`/`close`,
  not in the model: scored predictions (confidence > 0) must carry `components`
  (Invariant 8); `confirmed`/`refuted` require a `verification_run_id` that
  resolves to a real `verification_runs` row; `abandoned` requires no run because
  the loop cap is an outcome, not a verification.
- **Why:** ADR-0003 says only verification closes a record, but the model layer
  cannot see the database to check a run exists. The check belongs where the
  Session is. The model's terminal-only / no-double-close rules stay where they
  were already pinned by 11 tests.
- **Evidence:** `reliability/ledger/record.py:88-140`,
  `pytest tests/integration/test_ledger.py` → 14 passed
- **Status:** resolved

### 2. `eval:`-prefixed run ids are the harness's verifier identity (pre-S7 hole, documented)
- **Type:** decision
- **What:** `close()` accepts a `verification_run_id` starting with `eval:` without
  a `verification_runs` row. Corpus runs have no remediation, and `remediation_id`
  is `nullable=False`, so the harness cannot create an honest row.
- **Why:** rejecting all closes until S7 would block S3's exit criterion (the
  harness must close records). Alternative rejected: weakening the run-existence
  check for everyone. The escape hatch is narrow: a fixed prefix, plus
  `closed_by="evaluation-harness"`.
- **Evidence:** `reliability/ledger/record.py:57-59`,
  `test_eval_run_prefix_is_accepted_without_a_row`
- **Status:** open (owner: S7 — harden so only real verification runs can close
  once the verification engine exists)

### 3. Typed openers exist for the prediction types, engines adopt them later
- **Type:** change
- **What:** `open_diagnosis_prediction` / `open_risk_prediction` /
  `open_routing_prediction` in `reliability/ledger/record.py`. Each opens a
  pending record with payload, confidence and components.
- **Why:** S3's exit criterion is "every diagnosis, risk assessment and routing
  decision writes one at prediction time" — but those engines are S4/S5/S8. The
  obligation is already written into their package contracts (`reliability/
  diagnosis/__init__.py` line "every diagnosis writes a pending OutcomeRecord").
  Building the openers now means adoption is a one-line call, not a design task.
- **Evidence:** `test_diagnosis_risk_and_routing_all_open_pending`
- **Status:** resolved

### 4. The fixture-building logic moved out of conftest into the harness package
- **Type:** change
- **What:** `reliability/evaluation/fixtures.py::build_fixture_repo` now owns the
  copy + two-commit story for both fixtures; `tests/conftest.py` calls it.
- **Why:** the harness needed the same builder. One implementation of the git
  story means a fixture's history cannot drift between tests and evaluation.
- **Evidence:** `reliability/evaluation/fixtures.py`, `tests/conftest.py`
- **Status:** resolved

### 5. First harness run graded 0/10 -- the close used a stale object
- **Type:** finding
- **What:** `ledger.close()` returns the closed record, but `run_incident` read
  `record.status` from the pre-close object, so every incident reported
  "pending" and the summary counted 0 confirmed / 0 refuted.
- **Why:** `close()` deliberately does not mutate the caller's object (it closes
  a fresh hydration of the row, mirroring "corrections supersede, they do not
  overwrite"). Fixed by using the return value. Worth logging: the failure mode
  was a silent all-zero summary, not an exception — an assertion on outcomes
  would have caught it earlier than eyeballing the CLI line.
- **Evidence:** `reliability/evaluation/run.py` (`closed = ledger.close(...)`);
  re-run → "10 incidents: 10 confirmed, 0 refuted"
- **Status:** resolved

### 6. Harness verified: 10/10 confirmed, artifact stamped, deterministic
- **Type:** verification
- **What:** corpus of 10 incidents across 2 fixture repos; each runs the real
  investigation service, opens a prediction with components + cost, grades
  against `must_surface`, closes confirmed/refuted.
- **Why:** closes S3 exit criteria 3, 4 and 5.
- **Evidence:** `python -m reliability.evaluation.run --corpus tests/e2e/corpus`
  → `10 incidents: 10 confirmed, 0 refuted | 0 tokens | 425ms`;
  `pytest tests/e2e/` → 6 passed including
  `test_rerun_reproduces_the_artifact` (stable_view equality);
  full suite → **60 passed, 3 xfailed**
- **Status:** resolved

### 7. Token counts are honestly zero until Bob lands
- **Type:** finding
- **What:** per-incident `cost_tokens` is 0 for every corpus record; `cost_wall_ms`
  is measured. The artifact carries the field from the first write.
- **Why:** ERRATA A8 — cost cannot be reconstructed after the fact. There are no
  LLM calls in the S3 pipeline, so the truthful value is 0, not a made-up
  number. S4's adapter must populate it on its first real call.
- **Evidence:** artifact `summary.total_tokens: 0`;
  `tests/e2e/test_evaluation_harness.py::test_harness_runs_the_whole_corpus`
  asserts `>= 0`
- **Status:** open (owner: S4 — populate real token usage on first Bob call)

## Close-out

- **Shipped:** `outcome_records` table; `OutcomeLedger` with structural guards;
  typed prediction openers; accuracy/cost rollups (`reliability/ledger/query.py`);
  `auth_timeout` fixture; 10-incident corpus; evaluation harness CLI with
  `stable_view` determinism contract; 20 new tests.
- **Open threads:** #2 (`eval:` prefix hardening, S7), #7 (real token counts,
  S4). Carried over: 0001#7 Bob mechanism, 0001#8 ownership asymmetry,
  0002#7 deprecations, 0003#7 S1 xfail gaps.
- **Next session should:** S4 — Bob adapter, read paths only, and confirm the
  actual Bob integration mechanism with a working call (thread 0001#7) before
  anything downstream builds on the assumption.
- **Stage delta:** S3 NOT_STARTED → DONE
