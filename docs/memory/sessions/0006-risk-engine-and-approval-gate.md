---
session: 0006
title: Risk engine + approval gate
author: opencode (mimo)
stage: S5
started: 2026-09-26T17:46:00Z
ended: 2026-09-26T17:56:00Z
status: closed
---

## Context on entry

S4 had just closed (session 0005, `origin/main` = `3a94c0d`). S5's sharpest risk
was the one STAGES.md named: *how is "verified identity" sourced in this
environment?* The user chose the recommended option: *API-key operator registry*
(over HMAC-signed tokens and external OIDC). Exit criteria: factor breakdown,
reproducible levels, verified approval identity, HIGH/CRITICAL blocked from
`REMEDIATING`, and a proven no-bypass transition test.

## Entries

### 1. Approval identity = bearer API key resolving to an operators row
- **Type:** decision (closes S5's sharpest risk)
- **What:** new `operators` table (`id`, `name`, `api_key_hash` unique,
  `revoked_at`). `apps/api/auth.py` hashes the presented bearer key (sha256),
  looks up the row, and the route writes `operator_id`/`operator_name` from
  that row — never from the request body. `ApprovalCreate` now carries only
  `decision` + `reason`; a spoofed `approved_by`/`operator_id` in the body is
  ignored (pydantic extra=ignore). Bootstrap: first auth against
  `BRE_OPERATOR_KEY`/`BRE_OPERATOR_NAME` env creates the row lazily.
- **Why:** ERRATA A6 — free-text `approved_by` is not an identity; CLAUDE.md
  §4.5 requires the gate to be real. Hashed-at-rest keys avoid storing raw
  secrets (CLAUDE.md §6).
- **Evidence:** `tests/integration/test_risk_and_approval.py`
  (`test_approval_records_identity_from_key_not_body`,
  `test_approval_requires_bearer_key`,
  `test_auth_creates_operator_from_env_on_first_call`)
- **Status:** resolved — team invite/rotation story is still one key in env
  (demo-grade; revisit if S9 needs multi-operator attribution)

### 2. Schema migration note: approvals columns renamed
- **Type:** change (migration note per CLAUDE.md §6)
- **What:** `ApprovalDB.approved_by` → `operator_id` + `operator_name`
  (nullable, populated only via authenticated route); new `OperatorDB`.
  Tables are created by `create_all`, so an existing `bre.db` from before S5
  will keep the old column — drop `approvals`/`operators` locally or recreate
  the file. No teammates' DBs were touched (tests use throwaway tmp sqlite).
- **Why:** schema drift is called out as the #1 way this repo breaks.
- **Evidence:** `apps/api/database.py` (`ApprovalDB`, `OperatorDB`);
  `git diff` on `models/approval.py`
- **Status:** resolved

### 3. Deterministic classifier with an auditable factor breakdown
- **Type:** change
- **What:** `reliability/risk/classifier.py` — `RiskClassifier.classify()` maps
  severity / database_migration / api_surface_affected / blast_radius /
  tests_available / low_confidence to integer points
  (`THRESHOLDS = {CRITICAL: 7, HIGH: 4, MEDIUM: 2}`) and returns a
  `RiskAssessment` whose `factors = {score, thresholds, rules}` — every rule
  records its input and its points. No clock, no I/O, no randomness.
  `reliability/risk/policies.py` — `ApprovalPolicy.required_for(level)` →
  `AUTO` (LOW) | `HUMAN` (MEDIUM default, HIGH, CRITICAL).
- **Why:** Invariant 8 — a level without its breakdown is unauditable; S5
  criteria 1 + 2.
- **Evidence:** `test_classifier_returns_level_and_breakdown`,
  `test_classifier_is_reproducible` (three orderings → identical level +
  identical `factors`), `test_policy_table`
- **Status:** resolved

### 4. The gate is deny-by-default and wired into the transition entry point
- **Type:** change
- **What:** `reliability/orchestration/gate.py` — `assert_can_enter()` runs on
  every `POST /incidents/{id}/transition` and only inspects the
  `REMEDIATING` target. No assessment ⇒ level defaults to `CRITICAL` ⇒
  approval required. A qualifying approval must be `APPROVED`, have a non-null
  `operator_id`, match the *current* assessment's `risk_level`, and be
  `created_at >= assessment.created_at` (stale approvals don't survive
  re-assessment). Violations raise `GateViolation` → HTTP 403.
  Risk-level match is what keeps the no-assessment path honest: approvals
  created before any assessment are stamped `UNKNOWN` and can never satisfy a
  levelled gate.
- **Why:** S5 criteria 4 + 5; CLAUDE.md §4.5 — analysis is free, mutation is
  privileged.
- **Evidence:** `test_high_risk_requires_approval_to_remediate` (403 → approve
  → 200), `test_direct_transition_cannot_bypass_the_gate`
  (`RISK_ASSESSED → REMEDIATING` is a *legal* edge and still 403s),
  `test_unknown_risk_denies_remediation`, `test_rejected_approval_does_not_qualify`,
  `test_low_risk_passes_without_approval`
- **Status:** resolved

### 5. The S1 smoke test had to walk through the gate — that is the point
- **Type:** finding (behaviour change to an existing test)
- **What:** `test_happy_path_transitions` previously walked
  `... → REMEDIATING` with no risk assessment; the new gate correctly 403'd it.
  Rather than weakening the gate, the happy path now assesses risk, posts an
  authenticated approval, then continues — the state-machine test now models
  the real contract.
- **Why:** the gate exists precisely so that a bare transition call cannot
  reach `REMEDIATING` (criterion 5); a test that bypasses it would be pinning
  the vulnerability.
- **Evidence:** `tests/integration/test_api_smoke.py::test_happy_path_transitions`
- **Status:** resolved

### 6. New endpoints: assess-risk + approvals; ledger opens a risk prediction
- **Type:** change
- **What:** `POST /api/incidents/{id}/assess-risk` (body: optional
  `RiskContext`) classifies, persists `RiskAssessmentDB`, and calls
  `open_risk_prediction(...)` with `components = factors` — every risk level is
  a prediction (CLAUDE.md §4.4 / ADR-0003).
  `POST|GET /api/incidents/{id}/approvals` — creation requires the bearer key
  (401 without/with a wrong key).
- **Why:** the gate reads the persisted assessment; the ledger needs the
  prediction at assessment time, not at verification time (ERRATA A8 logic
  applied to risk).
- **Evidence:** `test_assess_risk_opens_ledger_prediction`
  (1 record, `prediction_type == "risk_level"`, `status == "pending"`,
  `components["score"] == factors["score"]`)
- **Status:** resolved

### 7. Timestamps: new code uses aware UTC, comparisons happen on loaded rows
- **Type:** verification (gotcha recorded)
- **What:** new files follow CLAUDE.md §6 (`datetime.now(timezone.utc)`), while
  pre-S5 code still uses `datetime.utcnow()`. SQLite's DATETIME renders both
  without offset and parses back naive, and the gate compares only DB-loaded
  rows (naive vs naive) — so no aware/naive comparison can occur in
  `qualifying_approval`. `models/risk.py` `RiskAssessment.id` also gained a
  `uuid4` default factory (the classifier constructs it without a DB id).
- **Why:** mixed naive/aware datetimes raise `TypeError` at compare time;
  worth pinning before someone "cleans up" one side only.
- **Evidence:** full suite green after the change (entry 8)
- **Status:** resolved — 0002#7 (deprecation thread) remains open for the old
  code

### 8. S5 exit criteria closed — suite green
- **Type:** verification (all five criteria)
- **What:** `python -m pytest tests/` → **87 collected, 84 passed,
  3 xfailed** (the 3 strict xfails still pin S1 gaps), exit code 0. New file
  `tests/integration/test_risk_and_approval.py` carries 12 tests covering
  every criterion; the smoke test (entry 5) covers the gate end to end.
- **Why:** STAGES.md — "no evidence, not done".
- **Evidence:** command above; test names per criteria in entries 1, 3, 4
- **Status:** resolved

## Close-out

- **Shipped:** `reliability/risk/{classifier,policies}.py`,
  `reliability/orchestration/gate.py`, `apps/api/auth.py`,
  `apps/api/routes/{approvals,risk}.py`, `OperatorDB` + reworked `ApprovalDB`,
  `models/approval.py` (identity removed from wire contract), gate hook in
  `routes/incidents.py`, 12 new tests + rewired smoke happy path.
- **Open threads:** 0005#1 (darwin host), 0001#8, 0002#7, 0003#7, 0004#2
  (S7 hardening) carry over. Nothing new opened; nothing closed.
- **Next session should:** S6 — remediation (write path): git checkpoint
  before any patch, changes on a branch (never the target's default), changed
  files recorded against the remediation record, repository allowlist enforced
  with a rejection test (STAGES exit criteria). The gate from S5 is the
  precondition: S6's write entry point must require `REMEDIATING`.
- **Stage delta:** S5 NOT_STARTED → DONE
