---
session: 0001
title: ASMOS alignment + workflow
author: "@dee (with Claude Opus 5)"
stage: S0
started: 2026-09-17T09:40:00Z
ended: 2026-09-17T10:35:00Z
status: closed
---

## Context on entry

Repo was Phase 1 only: domain models, an incident state machine, a SQLite schema, and two
FastAPI routers (incidents, investigations). `docs/ARCHITECTURE.md` described a full
reliability platform across 37 sections, of which roughly section 37 was real.

Belief on entry: ASMOS was a context/relevance engine that would slot into section 8 as a
file ranker. **That belief was wrong** — see entry #2. No prior sessions existed; this is
the first ledger entry, so there was nothing to catch up on.

## Entries

### 1. ARCHITECTURE.md audited against the code
- **Type:** finding
- **What:** Eight substantive problems and nine stale statements, written up in
  `docs/architecture/ERRATA.md`. The vision holds; several specifics do not.
- **Why:** The document is 2000 lines and reads as spec. Teammates and agents will build
  from it directly, so the wrong lines needed marking before anyone did.
- **Evidence:** `docs/architecture/ERRATA.md`; cross-checked against `models/incident.py:28`,
  `apps/api/database.py:103,116,127`.
- **Status:** resolved

### 2. Section 8 mischaracterises ASMOS
- **Type:** finding
- **What:** The doc models ASMOS as a relevance ranker producing scored *file* lists. The
  real ASMOS routes **agents** by learned per-(agent, topic) ownership, updated only on
  verified outcomes. Its own README states it does not beat RAG at span-retrieval QA and
  is not a QA-accuracy method.
- **Why:** This inverts the value of the asset. As written, section 8 uses ASMOS for the one
  task its authors measured it as losing, while discarding the mechanism that actually won.
- **Evidence:** ASMOS README.md; src/asmos/ownership/trust.py; src/asmos/routing/router.py.
- **Status:** resolved — replaced by `docs/architecture/ASMOS_INTEGRATION.md`

### 3. ASMOS already has a git bridge, and it has never been run to a result
- **Type:** finding
- **What:** `src/asmos/prototypes/git_ownership.py` runs the whole ASMOS mechanism over a
  real repository git history: merged-to-main = verified claim, detected revert = refuted.
  It builds checkpoints, sets verification, feeds the ownership runtime, returns a live
  router. It is marked as making no research claim, and has **no committed artifact** under
  `data/results/`.
- **Why:** This is the BRE integration shape, already written and already pointed at git. It
  is also an unclaimed result sitting in the other repo.
- **Evidence:** ASMOS/src/asmos/prototypes/git_ownership.py:160-210; a listing of
  ASMOS/data/results/ filtered for git returns nothing.
- **Status:** resolved

### 4. Decision: vendored bridge, not a package dependency
- **Type:** decision
- **What:** Re-implement the ASMOS pure math in `asmos_bridge/` rather than installing the
  `asmos` package.
- **Why:** ASMOS pulls chromadb, scikit-learn, numpy and optionally a ~2GB torch stack, and
  is organised for reproducers rather than consumers. A demo that dies on a model download
  is a lost demo. **Rejected:** taking the dependency (weight, fragility); ignoring ASMOS
  entirely (discards the only novel asset); using it as section 8 describes (invites the
  strongest objection for the weakest benefit).
- **Evidence:** ADR-0001; ASMOS/pyproject.toml dependency list.
- **Status:** resolved

### 5. Naming collision caught before it was built
- **Type:** decision
- **What:** ARCHITECTURE.md section 21 proposes a top-level `asmos/` package. The real
  ASMOS installs under the name `asmos`. A local package of that name shadows it silently.
  The directory is `asmos_bridge/`.
- **Why:** The failure mode is an editable install breaking in a way that looks like nothing.
- **Evidence:** ASMOS/pyproject.toml declares the project name as asmos.
- **Status:** resolved

### 6. The data model cannot close a prediction  *(the important one)*
- **Type:** finding
- **What:** `DiagnosisDB` never records whether the diagnosis was right. `RiskAssessmentDB`
  never records whether the level was appropriate. No table links a prediction to an outcome.
  Every accuracy metric in section 30 is therefore uncomputable, and the ASMOS ownership
  loop — whose only input is verified_correct / verified_total per source per topic — has
  nothing to consume.
- **Why:** Not a missing feature; a missing substrate. Everything claimed as differentiated
  sits on top of it.
- **Evidence:** `apps/api/database.py:66-93` — no verification or outcome column on either table.
- **Status:** resolved — `models/outcome.py` plus ADR-0003; pulled forward to stage S3

### 7. Bob integration mechanism is unverified
- **Type:** blocker
- **What:** No confirmed programmatic interface to IBM Bob. ARCHITECTURE.md section 16
  defers it deliberately, and every stage from S4 onward assumes it exists.
- **Why:** This is the single largest schedule risk in the project. If Bob cannot be driven
  programmatically in the hackathon environment, the orchestration layer has nothing to
  orchestrate.
- **Evidence:** none (hypothesis) — no call has been attempted.
- **Status:** open
- **Unblocked by:** one successful round-trip call to Bob from a script, capturing tokens
  and latency. Do this before anything else in S4.

### 8. Ownership asymmetry in real repos is assumed, not measured
- **Type:** question
- **What:** The routing story needs some sources to be reliably better than others on some
  components. ASMOS found asymmetry does **not** emerge organically in its constructed
  corpus. Code ownership intuitively is asymmetric, but that is not a result.
- **Why:** If asymmetry is absent, routing degenerates to permanent global-search fallback —
  correct behaviour, unconvincing demo.
- **Evidence:** none (hypothesis) — the ASMOS README states non-emergence for its own corpus;
  nothing measured on a real repo.
- **Status:** open
- **Answered by:** running git_ownership.py against a real repository and inspecting the
  asymmetry report. The instrument exists (entry #3).

### 9. Session memory protocol and stage tracker established
- **Type:** change
- **What:** Numbered append-only session ledger, five slash commands, a stage tracker with
  verifiable exit criteria, three ADRs, and a working agreement binding any agent to them.
- **Why:** Distributed team plus agents with no persistent context. The protocol deliberately
  mirrors the memory contract of the product itself — evidence on every entry, corrections
  supersede rather than overwrite — so the repo dogfoods its own thesis.
- **Evidence:** `CLAUDE.md`, `docs/memory/PROTOCOL.md`, `.claude/commands/` (5 files),
  `docs/stages/STAGES.md`, `docs/decisions/` (3 ADRs).
- **Status:** resolved

### 10. Nothing in this session was runtime-verified
- **Type:** verification
- **What:** `models/outcome.py` and `tests/unit/test_outcome_ledger.py` are syntax-checked
  only. Importing the models package fails with ModuleNotFoundError for pydantic. There is
  no venv in the repo and dependencies are not installed.
- **Why:** Logged rather than glossed. Eleven ledger invariants are written as tests and
  **none of them have been observed to pass.** Treat them as intent, not evidence.
- **Evidence:** importing models raises ModuleNotFoundError: No module named pydantic;
  no venv directory exists.
- **Status:** open
- **Unblocked by:** create a venv, install requirements.txt, then run pytest tests/unit -q

### 11. Build order corrected against ARCHITECTURE.md section 34
- **Type:** decision
- **What:** Risk and approval (S5) now precede remediation (S6); the outcome ledger (S3)
  precedes Bob integration (S4).
- **Why:** Section 34 puts the risk engine after Bob remediation, which builds the write path
  before the gate meant to guard it, contradicting section 24 of the same document. And
  predictions made before the ledger exists are permanently unlabelled; in a corpus of ten
  to thirty incidents, losing the first ten is most of the evidence.
- **Evidence:** `docs/stages/STAGES.md`; ERRATA A2, A3.
- **Status:** resolved

## Close-out

- **Shipped:** ARCHITECTURE.md audited (17 issues, documented rather than silently patched);
  ASMOS correctly characterised and its integration posture decided; session-memory protocol
  with 5 commands; stage tracker with command-shaped exit criteria; 3 ADRs; repo restructured
  into reliability / asmos_bridge / bob / connectors / tests with contracts in every package;
  the outcome ledger model and its test suite.
- **Open threads:** #7 Bob interface unverified (blocking S4, unassigned) · #8 ownership
  asymmetry unmeasured (blocking the S8 premise, unassigned) · #10 nothing runtime-verified
  (blocking S1 re-confirmation, unassigned)
- **Next session should:** create a venv, install requirements, and run pytest tests/unit.
  Thread #10 is cheap and it gates the credibility of everything written this session.
- **Stage delta:** S0 NOT_STARTED to DONE; S1 retroactively DONE; S2 is next
