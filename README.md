# Bob Reliability Engineer (BRE)

**Don't just generate a fix. Verify it — and learn who was right.**

AI coding agents like **IBM Bob** can write a fix in minutes. BRE is the layer that answers what every team asks next:
*was it right, was it safe, and did we learn anything?*

```
Detect → Investigate → Diagnose → Assess risk → Approve → Remediate → Verify → Learn
                                                                          │
                                       fails? roll back, refute, retry — capped, never unbounded
```

BRE does **not** reimplement Bob. It orchestrates it: Bob investigates and diagnoses read-only (`ask` mode) and edits files only in
`agent` mode, only after a human approves, only on a throwaway git branch, and only until a real test suite says the fix works.

> **Honest status, up front.** BRE has been built and tested end to end, but **it has never made a call to a live IBM Bob**. Until
> `python scripts/verify_bob.py` exits 0 on a machine with Bob Shell and an API key, every "Bob" step in the demo is a
> **labelled stand-in** and the dashboard says **SIMULATED BOB** on every screen. Everything else — git checkpoints and
> branches, the pytest verification, rollback, the approval gate, the ledger — is real. See
> [docs/submission/BOB_USAGE_PLAN.md](docs/submission/BOB_USAGE_PLAN.md).

---

## Try it (60 seconds, no Bob or credentials needed)

```powershell
# Windows — use CPython, NOT the msys2 python (see "Running it" below)
"$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
.\scripts\run_demo.ps1            # open http://127.0.0.1:8000
```
```bash
python3 -m venv venv && venv/bin/pip install -r requirements.txt && scripts/run_demo.sh
```

No repository of your own is needed: demo mode builds a throwaway git repository around a seeded failure. Prefer a terminal?
`python scripts/demo.py --twice`. The presenter guide is [docs/DEMO.md](docs/DEMO.md).

---

## What makes it different

**1. Verification is the only thing that closes a prediction.** Every diagnosis, risk level, routing decision and remediation plan
is written to an **outcome ledger** the moment it is made, as *pending*. Only a real verification run — a test suite exit code, not a model
grading itself — can mark it *confirmed* or *refuted*. A prediction that never reached verification is *abandoned* and moves nothing.

**2. It learns who was right, not who sounded right.** Built on the **ASMOS** mechanism: per-topic ownership learned only from
verification-backed outcomes (`Trust = (7 + verified_correct) / (10 + verified_total)`, `Ownership = 0.6·Trust + 0.4·Share`). When a
past diagnosis has earned it, BRE answers a recurring failure **from verified memory at zero Bob cost**; when it hasn't, it falls back to a full
investigation. The bridge is pinned to the real ASMOS source by 95 parity tests generated from ASMOS's own code.

**3. The write path is a safety argument, not a feature.** The order is the contract:

| Step | Enforced by |
|---|---|
| Analysis is free; mutation is privileged | Read-only unless the repository is on an **allowlist** (deny by default) |
| A human approves, and *who* is on the record | Approval identity comes from an **API key**, never from request text; HIGH/CRITICAL cannot reach `REMEDIATING` without one; the gate is re-checked inside the engine, so a hand-edited status column can't bypass it |
| Never on the default branch | Git **checkpoint** pinned first, then a fresh `bre/<incident>/attempt-<n>` branch; refuses a dirty tree |
| Changed files are facts | Recorded **from `git diff`**, never from what an agent says it changed |
| An agent can't cheat the suite | A **diff guard** rejects deleted / skipped / vacuous tests and CI-config edits, whatever the agent claims |
| Failure leaves nothing behind | Every failure past the checkpoint **rolls back exactly**, never touches the user's own untracked files, and keeps the rejected patch as evidence |
| The loop terminates | Attempt cap (default 3) → `ABANDONED`; per-call step budget; predictions from an attempt that never reached verification are *abandoned*, not *refuted* |
| One place writes | Exactly one `allow_writes=True` in the codebase (AST-tested) |

**4. It reports its own limits.** Every evaluation artifact states what is measured and what is nominal, includes look-alike
incidents on purpose, and reports flat and negative results as such (below).

---

## The demo in one paragraph

Create an incident → **Run**. BRE gathers evidence, has Bob diagnose it read-only, scores the risk with every factor visible, and stops at
**AWAITING APPROVAL** — nothing has touched the repository. A human approves with an operator key; BRE checkpoints, patches a branch,
and verifies at three levels (the failing test, its file, the whole suite). Create the *same* incident again and the diagnosis comes from
**memory at 0 tokens**, with the routing decision shown (`similarity 1.00 × ownership 0.42 = 0.42 ≥ τ`). Create the **look-alike** — same
symptom, different cause — and memory answers, the tests **refute** it, the patch is rolled back, the memory is excluded, and a full
investigation finds the real cause.

---

## Results — read the caveats

`python -m reliability.evaluation.compare` runs **Bob alone**, **BRE**, and an **ablation** over the same incidents through the real loop
(real git, real pytest). Full report: **[docs/RESULTS.md](docs/RESULTS.md)**. In brief:

| Scenario | What happened |
|---|---|
| Failures that **recur** (10 incidents, no look-alikes) | BRE served **6 of 10** diagnoses from verified memory, **0 refuted**, resolution identical, **24.8% lower nominal cost** |
| Corpus with **look-alike twins** (14 incidents, 4 of them look-alikes) | Similarity cannot separate a look-alike from a true match. BRE routed **13** attempts to memory and the test suite **refuted 4** of them (exactly the look-alikes): **4 wasted attempts**, each rolled back and then re-investigated. Resolution identical; still **10.1% lower nominal cost** (a correct reuse saves a diagnosis, a wrong one wastes one remediation) |
| Same corpus, τ tuned **without** look-alikes | Identical outcome — a wide range of τ routes the same incidents on this corpus |

The threshold is tuned by *simulating the routing policy that actually runs* (validated: it reproduces **9 of 9** measured runs exactly). An earlier tuner that scored
independent pairs said "never route" for the look-alike corpus; the measurement showed routing wins, so it was replaced — [ADR-0006](docs/decisions/ADR-0006-routing-sources-and-tau.md).

**Caveats that matter:** token figures are **nominal** while Bob is simulated (reuse, refutation and resolution counts are measured; token
totals are those counts × a placeholder price); the corpus is small, synthetic and the τ tuning is **in-sample**; ownership evolution is too
slow at ASMOS's prior strength to change behaviour on 14 incidents (the frozen-ownership ablation is flat — reported as such).
Decisions: [ADR-0005](docs/decisions/ADR-0005-bob-surfaces-and-replay.md), [ADR-0006](docs/decisions/ADR-0006-routing-sources-and-tau.md).

---

## Using it with real IBM Bob

```powershell
irm -Uri https://bob.ibm.com/download/bobshell.ps1 | iex        # Bob Shell; needs Node.js 24+
$env:BOB_API_KEY = "<key with Scope=Inference>"                 # never commit it
venv\Scripts\python.exe scripts\verify_bob.py                   # exit 0 + stamped artifact = the interface is real
$env:BRE_BOB_RECORD_DIR = "recordings"                          # keep Bob's real output
.\scripts\run_demo.ps1 -Live                                    # dashboard with LIVE IBM BOB
```

How BRE reaches Bob (`bob/`): `BobShell` drives `bob run --format json --mode ask|plan|agent`; a `Transport` contract lets the same adapter
use Bob Shell (preferred), an experimental read-only agent-host WebSocket, or the explicit-only replay stand-in.

---

## Layout

```
apps/api/        FastAPI: incidents, the loop (/advance, /detail), approvals, risk, ownership, results, demo
apps/web/        The dashboard (one file, no CDN)
reliability/     investigator · risk · remediation (the write path) · verification · ledger · orchestration (lifecycle, loop, routed) · evaluation
asmos_bridge/    ASMOS ownership / routing / verified memory / consolidation — pinned to real ASMOS by parity tests
bob/             IBM Bob: shell.py (documented `bob run`), transport.py, execution.py (agent host), replay.py + cassettes/, recording.py
connectors/      repository · git · tests · ci (read-only); git_history.py (ownership analysis)
models/          Pydantic domain models
tests/           unit · integration · e2e — real git repos, real pytest
scripts/         cockpit.py · demo.py · run_demo.* · tune_tau.py · verify_bob.py · gen_asmos_parity_vectors.py · measure_asymmetry.py
docs/            ARCHITECTURE (+ ERRATA) · decisions (ADRs) · memory (session ledger) · stages · submission · DEMO · RESULTS
```

---

## Running it

**Use CPython, not the msys2 Python.** On a machine with msys2/MinGW on PATH, a bare `python` may resolve to the msys2 build, which
creates a POSIX-layout venv and cannot `pip install` (its SSL has no trusted root store). Point at CPython explicitly, as above.

```bash
venv/Scripts/python.exe -m pytest                     # the full suite
venv/Scripts/python.exe scripts/cockpit.py --tests    # one-screen project status + integrity checks
venv/Scripts/python.exe -m reliability.evaluation.compare --orderings 3
```

API docs at `/docs` once the server is up. Configuration is environment variables — see [`.env.example`](.env.example).

---

## Working on this repository

This repo is built by a team plus agents whose context dies at the end of every session, so the **session ledger is the memory**:

| If you are... | Read |
|---|---|
| Any agent working on this repo | **[CLAUDE.md](CLAUDE.md)** — the working agreement. Not optional. |
| Joining, or returning after time away | `/cockpit` for state, then `/catch-up` (or [docs/memory/INDEX.md](docs/memory/INDEX.md) bottom-up) for the *why* |
| Wondering where the build is | [docs/STATUS.md](docs/STATUS.md) (generated), [docs/stages/STAGES.md](docs/stages/STAGES.md) |
| Reading the architecture | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — **and** its [ERRATA](docs/architecture/ERRATA.md) first |
| Wondering why something is the way it is | [docs/decisions/](docs/decisions/) |
| Submitting to the hackathon | [docs/submission/](docs/submission/) |

Every working session writes a numbered memory file under `docs/memory/sessions/`. A change that is not in the ledger effectively did not happen.

*MIT licensed. Built for the IBM Bob 2.0 Hackathon (lablab.ai).*
