---
session: 0003
title: Evidence collection end to end
author: opencode (mimo)
stage: S2
started: 2026-09-26T16:00:00Z
ended: 2026-09-26T17:05:00Z
status: closed
---

## Context on entry

Read in catch-up order: `docs/stages/STAGES.md`, `INDEX.md` (0001, 0002),
`docs/architecture/ERRATA.md`, the package contracts in `connectors/__init__.py`
and `reliability/investigator/__init__.py`, and `CLAUDE.md`. S1 was DONE with
20 passed / 3 xfailed. S2 was NOT_STARTED with no blockers. I had not read ADR-0001
or the ASMOS integration doc — S2 does not touch ASMOS, so this did not bite, but
the context was thinner than the protocol asks for.

## Entries

### 1. Connectors are plain dataclasses behind four classes
- **Type:** decision
- **What:** `RepositoryConnector`, `GitConnector`, `TestConnector`, `CIConnector` in
  `connectors/`, each returning dataclasses (`RepoSnapshot`, `GitCommitInfo`,
  `TestRunResult`, `CIFailureRecord`). No registry class yet.
- **Why:** a registry adds a lookup indirection with one implementation behind it.
  The `__init__.py` contract names four modules; adding a registry now would be
  speculative structure (ARCHITECTURE.md §33).
- **Evidence:** `connectors/repository.py`, `connectors/git.py`,
  `connectors/tests.py`, `connectors/ci.py`
- **Status:** resolved

### 2. Investigator persists through an injected store, not the ORM directly
- **Type:** decision
- **What:** `Investigator.investigate(..., store=EvidenceStore)` — a Protocol with
  one method, `add_evidence(investigation_id, item)`. The API service passes a
  SQLAlchemy-backed store; unit tests can pass an in-memory one.
- **Why:** the contract in `reliability/investigator/__init__.py` says the
  Investigator "writes evidence rows", but coupling the engine to `Session` would
  make it untestable without a database. The store protocol honours the contract
  while keeping the engine at arm's length from storage (and CLAUDE.md §6 wants
  logic in `services/`, not routes).
- **Evidence:** `reliability/investigator/investigator.py:44`,
  `apps/api/services/investigation_service.py:66`
- **Status:** resolved

### 3. Three GitPython API surprises, all found by tests not docs
- **Type:** finding
- **What:** (a) `commit.stats.files` is a `{path: counts}` dict — iterating it
  yields strings, so `item.a_path` raised `AttributeError`; (b) `Diff.diff`
  returns an empty value unless the diff is requested with `create_patch=True`;
  (c) `Repo.blame(rev, file)` yields `(commit, [line_text, ...])` groups, not
  per-line `(line, commit)` pairs.
- **Why:** each failed as an opaque AttributeError/AssertionError in
  `tests/unit/test_connectors.py`; the GitPython docs do not lead with these.
  Recorded so the next git-facing code does not rediscover them.
- **Evidence:** `tests/unit/test_connectors.py:54-81`,
  `pytest tests/unit/test_connectors.py` → 12 passed
- **Status:** resolved

### 4. Fixture git history is built at runtime; fixture test excluded from the suite
- **Type:** change
- **What:** `tests/conftest.py::seeded_repo` copies `tests/fixtures/seeded_failure/`
  to a tmp dir and creates the two-commit history there. `pytest.ini` gained
  `--ignore=tests/fixtures`.
- **Why:** git refuses to commit a nested `.git` directory, so the fixture tree
  cannot ship history; and the fixture's test fails **by design** (it is the
  seeded failure), so the main suite must never collect it.
- **Evidence:** `tests/conftest.py`, `pytest.ini:7`
- **Status:** resolved

### 5. POST /api/incidents/{id}/investigate verified end to end
- **Type:** verification
- **What:** The endpoint drives DETECTED → INVESTIGATING, runs the Investigator,
  persists evidence, completes the investigation and returns the package.
- **Why:** closes two S2 exit criteria — ≥5 evidence items across ≥3 source types,
  and a populated evidence set returned by the endpoint.
- **Evidence:** `pytest tests/` → **40 passed, 3 xfailed**; live run against
  uvicorn returned **9 evidence items across 5 source types** (3 repository,
  3 test, 1 config, 1 ci, 1 git) for the seeded connection-pool failure
- **Status:** resolved

### 6. Git evidence surfaces one commit for the two-commit fixture history
- **Type:** decision
- **What:** only the import commit appears as git evidence; the second commit
  (pool_size 20→2) touches only `config/app.yaml`, which is not in the candidate
  path list built from keyword path-matching, and `log_for_paths` is the query used
  when candidates exist.
- **Why:** the config diff is already carried by the config-evidence item, so the
  information is not lost — but a change confined to non-candidate paths will be
  invisible to git evidence. Acceptable for S2; revisit if S4 diagnosis quality
  suffers. Marking resolved rather than open: no action is owed by any stage.
- **Evidence:** live run output, `connectors/git.py` `log_for_paths`;
  fixture commit 2 modifies only `config/app.yaml`
- **Status:** resolved

### 7. S1's three xfail gaps remain xfailed
- **Type:** verification
- **What:** the new investigate endpoint sets `started_at` on *its own*
  investigation rows, but the old `POST /api/investigations` path was left
  untouched so the three strict xfails (missing incident FK, unset started_at,
  no DETECTED→CLOSED edge) still hold.
- **Why:** fixing them means updating ERRATA and the pinned tests — that is
  follow-up work, not S2 scope. A strict xfail that xpasses would have gone red
  here if I had accidentally fixed one.
- **Evidence:** `pytest tests/` → `tests/integration/test_api_smoke.py .........xxx`
- **Status:** open (owner: whoever picks up the ERRATA A5 state-machine fix)

## Close-out

- **Shipped:** four read-only connectors; TaskAnalyzer, EvidenceCollector and
  Investigator; investigation service; `POST /api/incidents/{id}/investigate`;
  seeded-failure fixture with runtime git history; 20 new tests
  (12 unit connector + 8 integration investigation).
- **Open threads:** #7 (S1 xfail gaps remain, pre-existing from 0002).
  Carried-over from 0001: #7 Bob mechanism unverified, #8 ownership asymmetry.
- **Next session should:** start S3 — the outcome ledger: `OutcomeRecord` model +
  table, prediction-time writes, and the ≥10-incident seeded corpus.
- **Stage delta:** S2 NOT_STARTED → DONE
