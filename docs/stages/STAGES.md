# Build Stages

Where the build actually is. Updated by `/stage` and at every `/session-end`.

**Status values:** `NOT_STARTED` · `IN_PROGRESS` · `BLOCKED` · `DONE`

A stage is `DONE` only when its exit criteria are met **and** the Evidence column names
the command output or session entry that proves it. No evidence, not done.

---

## Current position

| | |
|---|---|
| **Current stage** | S5 — Risk engine + approval gate |
| **Blocked on** | nothing (S4's darwin host gap is documented, not blocking: thread 0005#1) |
| **Sharpest risk** | S5 approval identity — how is "verified identity" sourced in this environment? |
| **Environment** | CPython 3.14.7 venv (macOS dev box); `python -m pytest` → 72 passed, 3 xfailed |

---

## Stage table

| ID | Stage | Depends on | Status | Evidence |
|---|---|---|---|---|
| S0 | Alignment + working agreement | — | `DONE` | session [0001](../memory/sessions/0001-asmos-alignment-and-workflow.md) |
| S1 | Foundation — models, state machine, DB, API | S0 | `DONE` | `pytest` → 20 passed, 3 xfailed — session [0002](../memory/sessions/0002-environment-verified.md) #4, #5 |
| S2 | Evidence collection — connectors + investigation engine | S1 | `DONE` | `pytest` → 40 passed, 3 xfailed — session [0003](../memory/sessions/0003-evidence-collection-end-to-end.md) #5 |
| S3 | Outcome ledger + evaluation harness | S1 | `DONE` | `pytest` → 60 passed, 3 xfailed; harness `10 incidents: 10 confirmed, 0 refuted` — session [0004](../memory/sessions/0004-outcome-ledger-and-harness.md) #6 |
| S4 | Bob adapter — **read paths only** | S2 | `DONE` | `pytest` → 72 passed, 3 xfailed; real CLI call `IBM Bob 1.126.0+bob2.1.0` — session [0005](../memory/sessions/0005-bob-interface-spike-and-adapter.md) #4, #7 |
| S5 | Risk engine + approval gate | S3, S4 | `NOT_STARTED` | — |
| S6 | Remediation — the write path | S5 | `NOT_STARTED` | — |
| S7 | Verification + rollback + bounded feedback loop | S6 | `NOT_STARTED` | — |
| S8 | ASMOS ownership routing + learning | S3, S7 | `NOT_STARTED` | — |
| S9 | Metrics, baseline comparison, demo | S8 | `NOT_STARTED` | — |

---

## Why this order differs from ARCHITECTURE.md §34

Two deliberate changes, both recorded in
[ADR-0003](../decisions/ADR-0003-outcome-ledger.md) and
[ERRATA](../architecture/ERRATA.md):

1. **The risk + approval gate (S5) comes before remediation (S6).** §34 puts the risk
   engine at Phase 5, *after* Bob remediation at Phase 4 — which builds the write path
   before the gate that is supposed to guard it. §24 of the same document says
   "Approve explicitly → Execute safely." The doc contradicts itself; the safety ordering
   wins.

2. **The outcome ledger (S3) is pulled early, before Bob integration.** Nothing downstream
   can learn or be measured without it, and retrofitting outcome records after the fact
   means the early incidents are unlabelled and unusable as training signal.

---

## Exit criteria

Criteria are written as commands with expected results. "Engine works" is not a criterion.

### S2 — Evidence collection
- [x] `RepositoryConnector` lists source files and detects project type for a target repo
      — `tests/unit/test_connectors.py::test_repository_lists_source_files`,
      `test_repository_detects_project_type`
- [x] `GitConnector` returns commit history, blame, and diffs for a named file
      — `test_git_recent_commits`, `test_git_blame`, `test_git_diff_for_commit_contains_pool_change`
- [x] `TestConnector` discovers tests and returns a structured pass/fail result
      — `test_test_discovery`, `test_test_run_returns_structured_result`
- [x] `CIConnector` parses a real CI failure log into a structured failure record
      — `test_ci_parses_real_failure_log`
- [x] `pytest tests/integration/test_investigation.py` passes and produces an evidence
      set of **≥5 items across ≥3 source types** for the seeded failure
      — 8 passed; live run: 9 items across 5 source types
- [x] `POST /api/incidents/{id}/investigate` returns a populated evidence set end to end
      — `test_investigate_seeded_failure_produces_evidence_package`

### S3 — Outcome ledger + evaluation harness
- [x] `OutcomeRecord` model + table; every diagnosis, risk assessment, and routing decision
      writes one at prediction time with `status=pending`
      — `tests/integration/test_ledger.py::test_diagnosis_risk_and_routing_all_open_pending`
- [x] Verification result closes the matching records to `confirmed` / `refuted`
      — `test_verification_pass_closes_all_pending_as_confirmed`,
      `test_verification_failure_refutes` (14 passed)
- [x] A seeded-failure corpus of **≥10 reproducible incidents** exists under `tests/e2e/corpus/`
      — 10 seeds across 2 fixture repos;
      `test_corpus_has_at_least_ten_reproducible_incidents`
- [x] `python -m reliability.evaluation.run --corpus tests/e2e/corpus` emits a stamped
      JSON artifact with per-incident outcome, token count, and wall time
      — live run: `10 incidents: 10 confirmed, 0 refuted | 0 tokens | 425ms`;
      `test_cli_emits_a_stamped_artifact`
- [x] Re-running the harness on an unchanged corpus reproduces the artifact (determinism)
      — `test_rerun_reproduces_the_artifact` (`stable_view` equality, two runs)

### S4 — Bob adapter (read paths only)
- [x] The actual Bob interface is **confirmed by a working call**, not assumed — closes
      thread 0001#7 — `probe_cli()` → `IBM Bob 1.126.0+bob2.1.0` from the installed
      binary; real lockfile format parsed (`test_probe_cli_calls_the_installed_bob_binary`,
      `test_discovery_parses_the_real_lockfile_format`); protocol recovered from shipped
      JS + binaries (session 0005 #3). Residual: live WS round trip blocked on darwin
      (no REH build published) — thread 0005#1
- [x] `BobAdapter.investigate()` and `.diagnose()` return structured output conforming to
      `models/diagnosis.py` — `test_investigate_returns_diagnosis_and_writes_ledger`,
      `test_diagnose_returns_diagnosis` (12 passed total)
- [x] Token usage per call is captured and written to the outcome ledger
      — `cost_rollup` asserts 1920 tokens (1500+420) + measured wall ms per call
- [x] No method in `bob/` can write to a target repository at this stage
      — four enforced ways: stubs raise, repo byte-hash test, source scan,
      public-surface test (session 0005 #6)

### S5 — Risk engine + approval gate
- [ ] `RiskClassifier` returns a level **plus its factor breakdown** (never a bare label)
- [ ] Risk level is reproducible: same inputs → same level, asserted in tests
- [ ] Approval records carry a verified identity, not a free-text `approved_by` string
- [ ] `HIGH` and `CRITICAL` cannot reach `REMEDIATING` without an approval row
- [ ] A test proves the gate cannot be bypassed by a direct state transition call

### S6 — Remediation (write path)
- [ ] A git checkpoint is created before any patch is applied
- [ ] Bob's changes land on a branch, never on the target's default branch
- [ ] Changed files are recorded against the remediation record
- [ ] Repository allowlist enforced; a write to a non-allowlisted repo is rejected in test

### S7 — Verification + rollback + bounded loop
- [ ] Targeted / component / regression levels run and are distinguishable in the result
- [ ] A verification failure transitions the incident to `REINVESTIGATING`
- [ ] The loop carries an attempt counter with a hard cap; a test proves it terminates
- [ ] Rollback restores the checkpoint and sets the remediation to `ROLLED_BACK`

### S8 — ASMOS ownership routing + learning
- [ ] Topic taxonomy derived from the target repo's structure
- [ ] Ownership updates **only** on a verification outcome (Invariant 3), asserted in test
- [ ] Routing decision records its components: similarity, ownership, τ, action
- [ ] τ tuned on the corpus, not hardcoded; the tuning run is a stamped artifact
- [ ] Cold-start and no-owner cases fall back to full investigation rather than misrouting

### S9 — Metrics + baseline + demo
- [ ] Baseline arm (Bob alone) and BRE arm run over the same corpus
- [ ] Cost per incident reported for both, with the ablation that isolates the cause
- [ ] Resolution rate reported with the seed count and variance, not a single run
- [ ] Any negative or flat result is reported as such

---

## Stage log

| Date | Stage | Change | Session |
|---|---|---|---|
| 2026-09-17 | S0 | NOT_STARTED → DONE | 0001 |
| 2026-09-17 | S1 | retroactively marked DONE (built before the tracker existed) | 0001 |
| 2026-09-17 | S1 | evidence attached — DONE is now verified, not assumed | 0002 |
| 2026-09-26 | S2 | NOT_STARTED → DONE — all six exit criteria closed by test evidence | 0003 |
| 2026-09-26 | S3 | NOT_STARTED → DONE — all five exit criteria closed by test evidence | 0004 |
| 2026-09-26 | S4 | NOT_STARTED → DONE — all four exit criteria closed; darwin host gap documented as thread 0005#1 | 0005 |
