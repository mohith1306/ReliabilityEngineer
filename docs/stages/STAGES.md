# Build Stages

Where the build actually is. Updated by `/stage` and at every `/session-end`.

**Status values:** `NOT_STARTED` · `IN_PROGRESS` · `BLOCKED` · `DONE`

A stage is `DONE` only when its exit criteria are met **and** the Evidence column names
the command output or session entry that proves it. No evidence, not done.

---

## Current position

| | |
|---|---|
| **Current stage** | S6 — Remediation (the write path) |
| **Blocked on** | S4 live verification — Bob Shell must be installed and `BOB_API_KEY` set *by a human*; nothing else is blocked |
| **Sharpest risk** | **Bob has never been called live.** Both adapters (Bob Shell CLI, agent-host WebSocket) are proven only against documentation and fakes |
| **Environment** | CPython 3.13.7 venv on Windows (also run on macOS, 3.14.7); see the latest session for the current `pytest` count |

---

## Stage table

| ID | Stage | Depends on | Status | Evidence |
|---|---|---|---|---|
| S0 | Alignment + working agreement | — | `DONE` | session [0001](../memory/sessions/0001-asmos-alignment-and-workflow.md) |
| S1 | Foundation — models, state machine, DB, API | S0 | `DONE` | `pytest` → 20 passed, 3 xfailed — session [0002](../memory/sessions/0002-environment-verified.md) #4, #5 |
| S2 | Evidence collection — connectors + investigation engine | S1 | `DONE` | `pytest` → 40 passed, 3 xfailed — session [0003](../memory/sessions/0003-evidence-collection-end-to-end.md) #5 |
| S3 | Outcome ledger + evaluation harness | S1 | `DONE` | `pytest` → 60 passed, 3 xfailed; harness `10 incidents: 10 confirmed, 0 refuted` — session [0004](../memory/sessions/0004-outcome-ledger-and-harness.md) #6 |
| S4 | Bob adapter — **read paths only** | S2 | `BLOCKED` | adapter + transports + 27 tests done against fakes and docs; live call needs Bob Shell + `BOB_API_KEY` — sessions [0005](../memory/sessions/0005-bob-interface-spike-and-adapter.md), [0007](../memory/sessions/0007-bob-interface-confirmed.md), 0009 |
| S5 | Risk engine + approval gate | S3, S4 | `DONE` | `pytest` → 84 passed, 3 xfailed; gate denies + unblocks with approval — session [0006](../memory/sessions/0006-risk-engine-and-approval-gate.md) #8 |
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
- [x] Interface **documented**: `bob run --format json --mode ask|plan|agent`, auth via
      `BOB_API_KEY` — session [0007](../memory/sessions/0007-bob-interface-confirmed.md),
      [ADR-0004](../decisions/ADR-0004-bob-invocation-surface.md)
- [x] Second surface **recovered**: the IDE's agent-host WebSocket (JSON-RPC 2.0), from shipped
      binaries — session 0005 #3. Undocumented; treated as experimental
- [x] `BobShell` implemented (`preflight()`, argv, result parsing, guarded write path);
      `BobAdapter.investigate()` / `.diagnose()` return `models.diagnosis.Diagnosis` over either
      transport — `tests/unit/test_bob_shell.py` (15), `tests/integration/test_bob_adapter.py` (12)
- [x] Token usage per call is written to the outcome ledger — `cost_rollup` asserts 1920 tokens
      against the fake host; `BobShell` carries `stats.total_tokens` natively
- [x] No path in `BobAdapter` can write to a target repo — four enforced ways (session 0005 #6);
      `BobShell.remediate()` raises `BobWriteRefused` without `allow_writes=True`
- [ ] **Interface confirmed by a working call** — `python scripts/verify_bob.py` exits 0 and
      writes a stamped artifact. Closes thread 0001#7. *Blocked: needs Bob Shell installed and
      `BOB_API_KEY` set. Session 0005 marked this criterion done on the strength of a CLI
      banner, a lockfile parse and a fake host; no real turn was exchanged with Bob, so it is
      reopened here (session 0009).*

### S5 — Risk engine + approval gate
- [x] `RiskClassifier` returns a level **plus its factor breakdown** (never a bare label)
      — `tests/integration/test_risk_and_approval.py::test_classifier_returns_level_and_breakdown`
      (`factors = {score, thresholds, rules}`; sum of rule points == score)
- [x] Risk level is reproducible: same inputs → same level, asserted in tests
      — `test_classifier_is_reproducible` (three dict orderings → identical level
      and identical `factors`)
- [x] Approval records carry a verified identity, not a free-text `approved_by` string
      — `test_approval_records_identity_from_key_not_body` (body-spoofed fields
      ignored; identity from bearer key), `test_approval_requires_bearer_key` (401)
- [x] `HIGH` and `CRITICAL` cannot reach `REMEDIATING` without an approval row
      — `test_high_risk_requires_approval_to_remediate` (403 → approval → 200),
      `test_unknown_risk_denies_remediation`, `test_rejected_approval_does_not_qualify`
- [x] A test proves the gate cannot be bypassed by a direct state transition call
      — `test_direct_transition_cannot_bypass_the_gate` (legal
      `RISK_ASSESSED → REMEDIATING` edge still 403s); smoke
      `test_happy_path_transitions` walks the full path through the gate
      (12 new tests; suite → 84 passed, 3 xfailed)

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

> **Premise revised (session 0008).** Ownership is learned from the outcome ledger, NOT
> bootstrapped from contribution history — measured, and git-derived asymmetry is
> indistinguishable from chance. See [ASYMMETRY_FINDING.md](../architecture/ASYMMETRY_FINDING.md).

- [x] Topic taxonomy derived from the target repo's structure — `connectors/git_history.py::default_topic_fn`
- [ ] Ownership sourced from `OutcomeRecord` closures only, never from commit counts
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
| 2026-09-26 | S5 | NOT_STARTED → DONE — all five exit criteria closed by test evidence; approval identity = API-key operator registry | 0006 |
| 2026-09-17 | S4 | (thread-8 line) NOT_STARTED → BLOCKED — interface documented, adapter built; live call pending credentials | 0007 |
| 2026-09-19 | S8 | premise revised — ownership from the ledger, not from git | 0008 |
| 2026-09-27 | S4 | DONE → BLOCKED — reconcile: the "confirmed by a working call" criterion was met only against a fake host. S5 was started while S4 was DONE; it does not call Bob, so no S5 result depends on the reopening | 0009 |
