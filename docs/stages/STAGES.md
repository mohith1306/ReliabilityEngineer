# Build Stages

Where the build actually is. Updated by `/stage` and at every `/session-end`.

**Status values:** `NOT_STARTED` · `IN_PROGRESS` · `BLOCKED` · `DONE`

A stage is `DONE` only when its exit criteria are met **and** the Evidence column names
the command output or session entry that proves it. No evidence, not done.

---

## Current position

| | |
|---|---|
| **Current stage** | none — S0–S3 and S5–S9 are DONE; **S4 is BLOCKED on a human** (live Bob call) |
| **Blocked on** | S4 live verification (and S6's live agent-mode call) — needs Bob Shell + `BOB_API_KEY` and a person, see `docs/submission/BOB_USAGE_PLAN.md` — Bob Shell must be installed and `BOB_API_KEY` set *by a human*; nothing else is blocked |
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
| S6 | Remediation — the write path | S5 | `DONE` | `pytest tests/integration/test_remediation.py` → 26 passed; suite 152 passed, 1 skipped — session 0009. **Caveat:** exercised through `ReplayExecutor`; `BobShellExecutor` (agent mode) has never run against a live Bob |
| S7 | Verification + rollback + bounded feedback loop | S6 | `DONE` | `pytest tests/e2e/test_reliability_loop.py` → 15 passed, `tests/unit/test_verification_units.py` → 8 passed; suite 175 passed, 1 skipped — session 0009. **Caveat:** run against real git repos and real pytest, with Bob replaced by its labelled replay stand-in |
| S8 | ASMOS ownership routing + learning | S3, S7 | `DONE` | `pytest tests/integration/test_asmos_routing.py` → 22 passed, `tests/unit/test_asmos_parity.py` → 95 passed (vectors generated from real ASMOS @ ee072ea), `tests/unit/test_route_simulation.py` → 12 passed; tau tuned on the corpus — `docs/artifacts/tau_tuning_full_20260926T205245Z.json` — session 0009 |
| S9 | Metrics, baseline comparison, demo | S8 | `DONE` | `tests/e2e/test_comparison_harness.py` → 8 passed; three stamped comparisons (`comparison_recurring_20260926T205900Z.json`, `comparison_full_20260926T210746Z.json`, `comparison_full_tau_from_recurring_20260926T211646Z.json`); report `docs/RESULTS.md` — session 0009. **Caveats:** token costs nominal (replayed Bob); the demo *video* and hosted URL are submission items (docs/submission/CHECKLIST.md), not exit criteria |

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
- [x] A git checkpoint is created before any patch is applied
      — `test_checkpoint_then_branch_never_the_default_branch` (`checkpoint_sha` == pre-patch HEAD, pinned
      under `refs/bre/checkpoints/*`)
- [x] Bob's changes land on a branch, never on the target's default branch
      — same test (`bre/<incident>/attempt-<n>`; default branch tip unmoved); `assert_on_bre_branch` guards every write
- [x] Changed files are recorded against the remediation record
      — `test_changed_files_are_recorded_from_git`, and `test_a_lying_executor_cannot_falsify_the_changed_files`
      (from `git diff`, never from the agent's claim)
- [x] Repository allowlist enforced; a write to a non-allowlisted repo is rejected in test
      — `test_a_repo_outside_the_allowlist_is_rejected_and_untouched`, `test_empty_allowlist_is_read_only_mode`
      (deny by default), `test_allowlist_cannot_be_escaped_with_dotdot`
- [x] *(added)* Every failure path rolls back exactly; rollback never deletes the user's own untracked files
      — `test_executor_crash_rolls_back_to_the_checkpoint`, `test_rollback_never_deletes_the_users_own_untracked_files`
- [x] *(added)* An agent cannot turn the suite green by weakening it: deleted / skipped / vacuous tests and
      CI-config edits are rejected on the diff, and the rejected patch is kept under `refs/bre/failed/*`
      — `test_deleting_the_failing_test_is_caught_rolled_back_and_kept_as_evidence`, `test_each_guard_rule_fires`
- [x] *(added)* The gate is re-checked inside the engine, so a hand-edited status column cannot bypass it
      — `test_engine_rechecks_the_gate_even_if_the_status_was_forced`
- [x] *(added)* The write path stays grep-able: exactly one `allow_writes=True` call site exists
      — `test_exactly_one_allow_writes_true_exists_outside_tests` (AST-based)

### S7 — Verification + rollback + bounded loop
- [x] Targeted / component / regression levels run and are distinguishable in the result
      — `test_the_three_levels_are_distinguishable_in_the_result` (`VerificationDB.levels` records each level's
      selectors and verdict; a failed level marks the later ones `skipped`, visibly)
- [x] A verification failure transitions the incident to `REINVESTIGATING`
      — `test_a_failed_verification_rolls_back_refutes_and_reinvestigates`
- [x] The loop carries an attempt counter with a hard cap; a test proves it terminates
      — `test_the_loop_terminates_at_the_attempt_cap` (a patch that can never work is tried exactly
      `BRE_MAX_ATTEMPTS`=3 times, then `ABANDONED`; the executor is invoked 3 times, never 4),
      `test_the_cap_is_configurable_and_never_below_one`
- [x] Rollback restores the checkpoint and sets the remediation to `ROLLED_BACK`
      — same tests: branch, HEAD and tree identical to the checkpoint; `refs/bre/failed/*` keeps the rejected patch
- [x] *(added)* Only verification closes outcomes: a passing run confirms them against a REAL `verification_runs` row;
      a failing run refutes them — `test_full_lifecycle_resolves_and_only_verification_closes_outcomes`
- [x] *(added)* An attempt that never reached verification is `abandoned`, not `refuted` — nothing tested it, so no
      reputation may move — `test_an_attempt_that_never_reached_verification_is_abandoned_not_refuted`
- [x] *(added)* No reproducing test => no verified fix (an unverifiable fix is not a verified one), and a run that
      collected zero tests is never a pass — `test_no_reproducing_test_means_no_verified_fix`,
      `test_a_run_that_ran_nothing_is_not_a_pass`
- [x] *(added)* A re-investigation is told what already failed — `test_the_next_diagnosis_is_told_what_already_failed`
- [x] *(added)* Analysis is free, mutation privileged: a HIGH-risk incident writes nothing until a human approves;
      every new assessment needs a new approval — `test_high_risk_incident_waits_for_a_human_and_nothing_is_written`

### S8 — ASMOS ownership routing + learning

> **Premise revised (session 0008).** Ownership is learned from the outcome ledger, NOT
> bootstrapped from contribution history — measured, and git-derived asymmetry is
> indistinguishable from chance. See [ASYMMETRY_FINDING.md](../architecture/ASYMMETRY_FINDING.md).

- [x] Topic taxonomy derived from the target repo's structure — `connectors/git_history.py::default_topic_fn`
- [x] Ownership sourced from `OutcomeRecord` closures only, never from commit counts
      — `OwnershipTable.from_ledger` joins to REAL `verification_runs` rows (excludes `eval:` closures, pending,
      abandoned, class C, non-diagnosis records): `test_only_verification_backed_diagnosis_closures_move_reputation`;
      `test_ownership_never_reads_git_history` (AST scan of `asmos_bridge/`)
- [x] Ownership updates **only** on a verification outcome (Invariant 3), asserted in test
      — `test_reputation_moves_on_verification_never_on_generation` (before/after); refutation lowers it:
      `test_memory_reuse_that_fails_verification_is_refuted_excluded_next_time_and_costs_trust`
- [x] Routing decision records its components: similarity, ownership, τ, action
      — `test_a_verified_memory_earns_a_route_and_the_decision_records_its_components`; written to the ledger as a
      `routing` prediction at decision time
- [x] τ tuned on the corpus, not hardcoded; the tuning run is a stamped artifact
      — `scripts/tune_tau.py` simulates BRE's actual sequential routing policy over 50 orderings and picks the tau with the highest mean net saving; artifacts `docs/artifacts/tau_tuning_recurring_20260926T205235Z.json` (recurring slice) and `docs/artifacts/tau_tuning_full_20260926T205245Z.json` (full corpus). The simulator is validated against the measured end-to-end runs: **9 of 9 orderings agree exactly** (`docs/artifacts/simulator_validation_*.json`). An earlier pair-based tuner was wrong and was replaced (ADR-0006 "Rejected")
- [x] Cold-start and no-owner cases fall back to full investigation rather than misrouting
      — `test_cold_start_falls_back_to_full_investigation`, `test_a_dissimilar_incident_falls_back_rather_than_misrouting`,
      `test_memory_from_another_topic_is_invisible`
- [x] *(added)* The bridge returns exactly what real ASMOS returns — `tests/unit/test_asmos_parity.py`, 95 vectors
      generated from ASMOS's own source by `scripts/gen_asmos_parity_vectors.py` (ADR-0001's condition for vendoring)
- [x] *(added)* End to end on real git repos: the 2nd similar incident is served from verified memory at 0 Bob tokens
      and fixed + tested; a look-alike whose real cause differs is refuted, the memory is excluded on the retry, and its
      ownership drops — `test_the_second_similar_incident_is_served_from_verified_memory_at_zero_bob_tokens`
- [x] *(added)* Memory holds only what a passed verification run vouched for; corrections supersede, never overwrite
      — `test_memory_refuses_anything_not_backed_by_a_passed_run`, `test_corrections_supersede_and_never_overwrite`

### S9 — Metrics + baseline + demo
- [x] Baseline arm (Bob alone) and BRE arm run over the same corpus
      — `python -m reliability.evaluation.compare`: same incidents, same order, fresh DB and fresh git repos per arm, through the real loop
- [x] Cost per incident reported for both, with the ablation that isolates the cause
      — `docs/RESULTS.md`; the `bre_frozen` arm (ownership frozen at its prior) is ASMOS's own single-variable ablation. **Result: flat** —
      one refutation moves trust ≈0.03 at ASMOS's prior strength, so ownership evolution does not change behaviour on 14 incidents. Reported as such
- [x] Resolution rate reported with the seed count and variance, not a single run
      — 3 orderings per slice (mean ± std), 50 in the tuner; paired differences vs baseline
- [x] Any negative or flat result is reported as such
      — the flat ablation; the cost of forced/out-of-distribution routing (wasted attempts); and my own earlier tuner that returned "never route" where routing wins (ADR-0006)

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
| 2026-09-27 | S6 | NOT_STARTED → DONE — all four exit criteria plus four added safety criteria closed by test evidence; run through the replay executor only | 0009 |
| 2026-09-27 | S7 | NOT_STARTED → DONE — all four exit criteria plus five added criteria closed by test evidence; Bob replay stand-in | 0009 |
| 2026-09-27 | S8 | NOT_STARTED → IN_PROGRESS — router, ledger-derived ownership, verified memory, consolidation and ASMOS parity done; tau tuning on the corpus pending | 0009 |
| 2026-09-27 | S8 | IN_PROGRESS → DONE — tau tuned on the corpus; simulator validated against measured runs | 0009 |
| 2026-09-27 | S9 | NOT_STARTED → DONE — three-arm comparison over 3 slices, ablation flat and reported as such | 0009 |
