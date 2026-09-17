# Build Stages

Where the build actually is. Updated by `/stage` and at every `/session-end`.

**Status values:** `NOT_STARTED` · `IN_PROGRESS` · `BLOCKED` · `DONE`

A stage is `DONE` only when its exit criteria are met **and** the Evidence column names
the command output or session entry that proves it. No evidence, not done.

---

## Current position

| | |
|---|---|
| **Current stage** | S2 — Evidence Collection |
| **Blocked on** | S4 live verification — needs Bob Shell installed and `BOB_API_KEY` set |
| **Sharpest risk** | S8 — ownership asymmetry is still assumed, not measured (thread 0001#8) |
| **Environment** | CPython 3.13.7 venv; `venv/Scripts/python.exe -m pytest` → 35 passed, 3 xfailed |

---

## Stage table

| ID | Stage | Depends on | Status | Evidence |
|---|---|---|---|---|
| S0 | Alignment + working agreement | — | `DONE` | session [0001](../memory/sessions/0001-asmos-alignment-and-workflow.md) |
| S1 | Foundation — models, state machine, DB, API | S0 | `DONE` | `pytest` → 20 passed, 3 xfailed — session [0002](../memory/sessions/0002-environment-verified.md) #4, #5 |
| S2 | Evidence collection — connectors + investigation engine | S1 | `NOT_STARTED` | — |
| S3 | Outcome ledger + evaluation harness | S1 | `NOT_STARTED` | — |
| S4 | Bob adapter — **read paths only** | S2 | `BLOCKED` | adapter + 15 tests done; needs Bob Shell + `BOB_API_KEY` for the live call |
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
- [ ] `RepositoryConnector` lists source files and detects project type for a target repo
- [ ] `GitConnector` returns commit history, blame, and diffs for a named file
- [ ] `TestConnector` discovers tests and returns a structured pass/fail result
- [ ] `CIConnector` parses a real CI failure log into a structured failure record
- [ ] `pytest tests/integration/test_investigation.py` passes and produces an evidence
      set of **≥5 items across ≥3 source types** for the seeded failure
- [ ] `POST /api/incidents/{id}/investigate` returns a populated evidence set end to end

### S3 — Outcome ledger + evaluation harness
- [ ] `OutcomeRecord` model + table; every diagnosis, risk assessment, and routing decision
      writes one at prediction time with `status=pending`
- [ ] Verification result closes the matching records to `confirmed` / `refuted`
- [ ] A seeded-failure corpus of **≥10 reproducible incidents** exists under `tests/e2e/corpus/`
- [ ] `python -m reliability.evaluation.run --corpus tests/e2e/corpus` emits a stamped
      JSON artifact with per-incident outcome, token count, and wall time
- [ ] Re-running the harness on an unchanged corpus reproduces the artifact (determinism)

### S4 — Bob adapter (read paths only)
- [x] Interface **documented**: `bob run --format json --mode ask|plan|agent`, auth via
      `BOB_API_KEY` — session 0003, [ADR-0004](../decisions/ADR-0004-bob-invocation-surface.md)
- [x] `BobAdapter` implemented with `preflight()`, argv construction and result parsing;
      15 unit tests against the documented schema
- [x] Write path guarded: `remediate()` raises `BobWriteRefused` without `allow_writes=True`
- [ ] **Interface confirmed by a working call** — `python scripts/verify_bob.py` exits 0
      and writes a stamped artifact. Closes thread 0001#7. *Blocked: Bob Shell not
      installed, `BOB_API_KEY` not set.*
- [ ] `investigate()` / `diagnose()` return output conforming to `models/diagnosis.py`
      (needs a prompt + response schema, which needs a live Bob to iterate against)
- [ ] Token usage per call written to the outcome ledger

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
| 2026-09-17 | S4 | NOT_STARTED → BLOCKED — interface documented and adapter built; live call needs credentials | 0003 |
