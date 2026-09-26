# lablab.ai submission — IBM Bob 2.0 Hackathon

Copy each block into the matching form field. Anything marked **`[TEAM: …]`** cannot be truthfully filled in until a person has done the
thing it names (see [BOB_USAGE_PLAN.md](BOB_USAGE_PLAN.md)). **Delete any sentence you cannot back with an artifact in this repository.**
Deadline: **Sun 2026-09-27, 11:00 AM EDT = 20:30 IST.**

---

## 1 · Project title

**Bob Reliability Engineer (BRE)**

## 2 · Short description  *(≈250 characters)*

BRE wraps IBM Bob in a safety-and-learning loop: evidence first, writes gated on an authenticated human, fixes applied on a git branch and verified by the real test suite, failures rolled back, and memory that learns which diagnosis sources are verifiably right.

## 3 · Long description

**The problem.** AI coding agents can write a fix in minutes. Teams then face three questions the agent cannot answer about itself: *Was the fix right? Was it safe to apply? Did we learn anything for next time?* Today the answers are a human's gut feeling, a green CI run that may have been made green by weakening the tests, and nothing at all.

**What BRE does.** BRE is a reliability layer around IBM Bob — it orchestrates Bob; it does not reimplement it. For an incident it runs:

`Detect → Investigate → Diagnose → Assess risk → Approve → Remediate → Verify → Learn`

- **Evidence before action.** Connectors gather repository, git, test and CI evidence. Bob diagnoses **read-only** (`ask` mode).
- **Auditable risk.** A deterministic classifier returns a level *and every factor's points*. A score without its breakdown is not accepted anywhere.
- **A real approval gate.** HIGH/CRITICAL changes cannot proceed without an approval whose *identity comes from an API key*, never from request text. Deny by default; re-checked inside the write engine.
- **A write path built as a safety argument.** Allowlisted repositories only; a pinned git checkpoint; a fresh `bre/*` branch (never the default); changed files recorded *from `git diff`*; a diff guard that rejects deleted, skipped or vacuous tests and CI-config edits; exact rollback on any failure that never touches the user's own untracked files. One `allow_writes=True` exists in the whole codebase.
- **Verification as the only thing that closes a prediction.** Three levels — the previously failing test, its whole file, the entire suite — fail-fast. "No reproducing test" means *no verified fix*. A capped loop (default 3 attempts) ends in `ABANDONED` rather than running forever.
- **Learning that cannot be talked into.** Every diagnosis, risk level and routing decision is written to an **outcome ledger** as *pending* when it is made and closed only by a real verification run. Built on the **ASMOS** mechanism, BRE learns per-topic *ownership* — who has been verifiably right about what — and answers a recurring failure **from verified memory at zero Bob cost** when a memory has earned it, otherwise runs a full investigation. The ASMOS math is pinned to the real research code by 95 parity tests.

**Measured, and honest about it.** On failures that recur, BRE served 6 of 10 diagnoses from verified memory with none refuted (≈25% lower *nominal* cost). On a corpus seeded with **look-alike incidents** (same symptom, different cause) BRE routed 13 attempts to memory and the test suite refuted 4 of them — exactly the look-alikes — each patch rolled back, the memory's ownership lowered, and a full investigation run instead; resolution matched Bob alone, and nominal cost was still ~10% lower. Similarity alone cannot separate a look-alike from a true match — that is exactly why verification is the gate. Token figures are *nominal* while Bob is simulated; the report ([docs/RESULTS.md](../RESULTS.md)) says so on every table and reports flat and negative results as found.

**Business value.** Fewer wasted agent attempts and tokens on failures the team has already solved; an audit trail for every AI-authored change (who approved, what was verified, what was rolled back); and a safe way to let agents act on production-adjacent code — because the control is structural, not a request in a prompt.

**Originality.** Applying verification-gated reputation (ASMOS) to reliability engineering, where the verifier is a *deterministic test-suite exit code* rather than an LLM grading itself; treating "the agent was wrong and the system found out" as the headline feature rather than the failure case; and an evaluation that includes the adversarial case on purpose.

## 4 · IBM Bob usage statement

> **[TEAM: replace every bracket below with what actually happened. If Task A/B have not been done, keep only the first paragraph and say plainly that Bob integration is implemented but not yet exercised live.]**

BRE is designed around IBM Bob as its engineering capability. The `bob/` package drives **Bob Shell** non-interactively (`bob run --format json --mode ask|plan|agent`): `ask` mode for read-only investigation and diagnosis, and `agent` mode **only** for remediation and **only** behind BRE's approval gate, allowlist, git checkpoint and diff guard. Bob's own token and cost report (`stats`) is written into BRE's outcome ledger on every call.

**[TEAM: Task A — "We installed Bob Shell and ran `scripts/verify_bob.py`; it exited 0 and wrote `docs/artifacts/bob_roundtrip_<stamp>.json` (tokens, cost, task id)."]**

**[TEAM: Task B — "We ran the full loop with live Bob on a seeded failing repository; Bob's real prompts and replies are in `recordings/`. What differed from the documented contract: …"]**

**[TEAM: Task C — "Each of us used Bob (IDE, Ask/Plan mode) to review BRE's write-path safety design; the findings are in `docs/submission/bob_review_<name>.md` and the ones we agreed with became failing tests, then fixes: …"]**

**[TEAM: Task D — "Bob (Code mode) authored the fourth scenario: `tests/fixtures/<name>/`, `bob/cassettes/<name>.json`, `tests/e2e/corpus/seed-015.json`. Task-session screenshots: `docs/submission/screenshots/`."]**

**Disclosure.** Parts of this repository were developed with other AI coding assistants (Claude Code, opencode); the session ledger under `docs/memory/sessions/` records which. Where the demo runs without a live Bob, the dashboard shows **SIMULATED BOB** on every screen and the replay stand-in is documented in [ADR-0005](../decisions/ADR-0005-bob-surfaces-and-replay.md).

## 5 · Technology & category tags

`IBM Bob` · `Bob Shell` · `Python` · `FastAPI` · `pytest` · `Git` · `SQLite` · `SQLAlchemy` · `Pydantic` · `ASMOS` · `Claude Code` *(development assistant, disclosed)* ·
Categories: **DevOps / SRE**, **AI agents & agent safety**, **Developer tools**, **Reliability engineering**

## 6 · Public code repository

`https://github.com/mohith1306/ReliabilityEngineer` — **public** (verified with `gh repo view`).
**[TEAM: the reconciled work lives on the local branch `integration/reconcile-main` and is NOT pushed. Push it and merge to `main` before submitting, or the judges see the old repository.]**

## 7 · Bob task-session summary screenshots (each team member)

**[TEAM: required. `docs/submission/screenshots/<name>/` — see BOB_USAGE_PLAN.md "What to screenshot".]**

## 8 · Demo application platform · 9 · Application URL

- **Platform:** **[TEAM: e.g. Render (`render.yaml` provided) / Railway / Hugging Face Spaces (Docker)]**
- **URL:** **[TEAM: after deploy]**
- The hosted instance runs the **simulated-Bob** demo image (`Dockerfile`); the live-Bob demo is local. The `Dockerfile` has **never been built** (Docker Desktop was not running when it was written) — build it once before relying on it: `docker build -t bre . && docker run --rm -p 8000:8000 bre`.

## 10 · Cover image

`docs/submission/cover.png` (1280×720).

## 11 · Video demonstration

Script: [VIDEO_SCRIPT.md](VIDEO_SCRIPT.md). **[TEAM: record; say in the first 15 seconds whether the run is LIVE or SIMULATED.]**

## 12 · Slide presentation

`docs/submission/BRE_pitch.html` (open in a browser; **Ctrl+P → Save as PDF**, landscape, margins none, background graphics on) — 16:9, one slide per page.
**[TEAM: review, then own the pitch.]**
