---
session: 0004
title: Asymmetry measured, premise refuted
author: "@dee (with Claude Opus 5)"
stage: S2
started: 2026-09-19T14:30:00Z
ended: 2026-09-19T15:50:00Z
status: closed
---

## Context on entry

Read the 0001-0003 close-outs and the stage tracker. Took thread 0001#8 because #7 is
blocked on credentials nobody has yet, and because ADR-0001 records #8 as a risk that must
be measured *before* S8 is built on it.

Belief on entry: ownership asymmetry probably does exist in real repos — code ownership is
intuitively asymmetric, that is what git blame measures. That belief was wrong.

## Entries

### 1. Session 0003's work never reached main
- **Type:** blocker
- **What:** PR #1 was merged at commit `89460d2`. Commit `3ddcc73` — the entire Bob adapter
  session — was pushed to the branch *after* the PR had already been merged, so it was
  never included. `bob/adapter.py`, `scripts/verify_bob.py`, `tests/unit/test_bob_adapter.py`,
  ADR-0004 and session 0003 were all stranded.
- **Why:** Found only because `scripts/` did not exist when this session tried to write
  into it. Nothing warned. A merged PR does not close its branch, and pushing to a merged
  branch silently does nothing useful.
- **Evidence:** `git merge-base --is-ancestor 3ddcc73 origin/main` → false;
  `git log --oneline origin/main` shows `699c463, 89460d2, 376d929` with no `3ddcc73`.
- **Status:** resolved — cherry-picked onto `thread-8-ownership-asymmetry` as `9248c7c`;
  suite back to 35 passed, 3 xfailed before this session's own work began

### 2. Identity aliasing in real git history is far worse than expected
- **Type:** finding
- **What:** ASMOS's 226 commits carry **17 distinct (name, email) pairs for 4 people**. One
  contributor appears under two names sharing a GitHub noreply address; another under one
  name spread across eight emails, six of them `user@hostname` from different MacBooks;
  a third has a curly quote inside the email address itself, making it differ from their
  real address by one invisible character.
- **Why:** The upstream prototype keys agents on the raw author name. Neither name nor
  email alone identifies a person, so any ownership measure built on either is computed
  over the wrong agent set.
- **Evidence:** `git log --format="%an|%ae" | sort -u` on the ASMOS checkout;
  `connectors/git.py::resolve_identities` resolves 17 pairs → 4, and 3 → 2 on the dental repo.
- **Status:** resolved

### 3. Git connector built, with identity resolution
- **Type:** change
- **What:** `connectors/git.py` (324 lines). Shells out to git rather than taking the
  declared gitpython dependency — four stable plumbing calls, no library assumptions.
  `resolve_identities` treats identity as connected components over a bipartite name/email
  graph: two pairs are the same person if they share a name **or** an email, transitively.
  Topics are derived from directory structure rather than hardcoded, since BRE must run
  against repositories it has never seen.
- **Why:** Stage S2 needs this regardless, and ADR-0001 rules out importing ASMOS's version.
- **Evidence:** `connectors/git.py`; 18 unit tests in `tests/unit/test_git_connector.py`.
- **Status:** resolved

### 4. The premise is REFUTED — NO-GO on all four repositories
- **Type:** verification
- **What:** Claim events fed into `asmos.e6.asymmetry` **unmodified**. Against ASMOS's own
  pre-registered criterion (OCI ≥ 0.70 and p < 0.001), every repository fails:
  ASMOS 0.862 / null 0.813 / p 0.033; Dental 0.767 / null 0.731 / p 0.103;
  PAY 1.000 / null 1.000 / p 1.000; BRE 0.924 / null **0.929** / p 0.715.
- **Why:** The observed OCI looks strong everywhere and is indistinguishable from chance
  everywhere. High concentration is an artifact of having very few contributors, which is
  exactly what the permutation null exists to catch. BRE's own observed value sits *below*
  its null.
- **Evidence:** `venv/Scripts/python.exe scripts/measure_asymmetry.py`;
  `docs/artifacts/asymmetry_20260919_154301.json`; identical across runs (seed=42).
- **Status:** resolved — closes thread 0001#8 with a negative result

### 5. The single-author control validates the instrument
- **Type:** verification
- **What:** PAY, one contributor: OCI exactly 1.000, null exactly 1.000, p = 1.0.
- **Why:** Perfect apparent concentration carrying zero information — the clearest possible
  demonstration that a raw OCI must never be quoted without its null. Had this control been
  omitted, 1.000 would have read as the strongest result in the sweep.
- **Evidence:** same artifact, `results.PAY`.
- **Status:** resolved

### 6. Zero refutation events in 852 commits
- **Type:** finding
- **What:** Not a single `Revert "..."` commit across all four repositories.
- **Why:** The upstream prototype models a detected revert as the refutation signal. In
  real history that signal does not occur at all, so the verified/refuted loop cannot be
  fed from git. This is the most consequential finding of the session and it cuts in BRE's
  favour: BRE *manufactures* refutation on every failed verification, which git never
  records. BRE is not mining a signal that was already there — it is creating one that
  was not.
- **Evidence:** `n_refutations: 0` for every repo in the artifact;
  `git log --grep="^Revert" | wc -l` → 0 on ASMOS.
- **Status:** resolved

### 7. My own prediction failed
- **Type:** verification
- **What:** I expected unresolved identities to materially understate concentration. The
  direction held (5 apparent agents vs 4 real) but the magnitude was negligible — OCI 0.862
  either way, because the aliased identities were low-volume contributors.
- **Why:** Logged because entry #2 and #3 would otherwise read as though the identity work
  rescued the measurement. It did not. The resolution is still correct and still needed for
  S8; it simply did not change this result, and implying otherwise would be exactly the
  confident nonsense the evidence rule exists to prevent.
- **Evidence:** normalized vs raw rows in the artifact differ by < 0.001 OCI.
- **Status:** resolved

### 8. Decision: ownership is learned from the outcome ledger, not bootstrapped from git
- **Type:** decision
- **What:** S8 will not use contribution history as an ownership source. A git-derived
  prior may be used for cold start, but only labelled as indistinguishable from chance at
  small N. Written up in `docs/architecture/ASYMMETRY_FINDING.md`.
- **Why:** Commit authorship measures who *writes* a subsystem; the routing mechanism needs
  who is verifiably *right* about it. More decisively, BRE's agents are not humans at all —
  they are diagnosis sources (Bob, prior incidents, analyzers), none of which appear in
  commit history. **Rejected:** using git blame as the ownership prior (measured, chance-
  indistinguishable); abandoning the ASMOS angle (the result relocates the signal, it does
  not remove it).
- **Evidence:** `docs/architecture/ASYMMETRY_FINDING.md`; ADR-0001 risk section updated.
- **Status:** resolved

## Close-out

- **Shipped:** Thread 0001#8 closed with a **negative result**, which is the useful kind.
  `connectors/git.py` with identity resolution (18 tests), `scripts/measure_asymmetry.py`,
  a stamped reproducible artifact, and `ASYMMETRY_FINDING.md`. Recovered session 0003's
  stranded commit. Suite: 50 passed, 3 xfailed.
- **Open threads:** #7 Bob live call (blocked on credentials) · 0002#7 deprecations
  filtered not fixed · 0003#11 possible TLS interception · **0004#9 (new)** the asymmetry
  test has almost no power at 1–4 agents; a 50+ contributor repo is the decisive follow-up
  and was not run
- **Next session should:** start S2 properly — `connectors/repository.py` and
  `connectors/tests.py`, then the investigation engine. The git connector is already
  written, so S2 is now roughly half done. Everything needed for it is unblocked.
- **Stage delta:** S2 NOT_STARTED → IN_PROGRESS (git connector complete);
  S8 premise revised — ownership learned from the ledger, not from git
