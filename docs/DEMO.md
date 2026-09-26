# Running and presenting the demo

## 60 seconds to a running dashboard

```powershell
# Windows -- use CPython, NOT the msys2 python (see README "Running it")
"$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
.\scripts\run_demo.ps1                 # http://127.0.0.1:8000  (simulated Bob)
```
```bash
# macOS / Linux
python3 -m venv venv && venv/bin/pip install -r requirements.txt
scripts/run_demo.sh
```
```bash
# Docker (untested on the dev machine -- Docker Desktop was not running; treat as unverified until built once)
docker build -t bre . && docker run --rm -p 8000:8000 bre
```

No repository of your own is needed: **demo mode** manufactures a throwaway git repository from a seeded failure and opens
an incident against it. Fallback with no browser at all: `python scripts/demo.py --twice`.

## Read the mode pill before you say anything

The top-right pill is the truth about what is running:

| Pill | Meaning | What you may say |
|---|---|---|
| **SIMULATED BOB** (amber) | Bob is replaced by a labelled replay stand-in. Git, pytest, the gate, the ledger are real. | "The agent here is a stand-in. Verification is real." |
| **LIVE IBM BOB** (green) | Bob Shell is being called. | "Bob is diagnosing and fixing this." — but only after `scripts/verify_bob.py` has exited 0 |
| NO BOB (red) | Nothing can diagnose. | Fix the environment first. |

Never present a SIMULATED run as Bob's work. The judges can read the pill.

## Five-minute presenter script

Reset first (**Reset** button) so the story is clean.

**1 · The problem (30 s).** AI agents will write fixes. Teams can't answer: *was it right, is it safe, and did we learn?*
BRE wraps Bob with exactly those answers.

**2 · Scenario 1, "Connection pool exhaustion" (≈90 s).** Create the incident → **Run the loop**.
- It stops at **AWAITING APPROVAL**. Point at *Risk & approval*: HIGH, with every factor's points. *"A score with no breakdown is unauditable."*
- Point at the repo: **nothing has been written.** *"Analysis is free; mutation is privileged."*
- Paste the operator key (shown next to the button), **Approve**. *"The record stores who, from the key — never from a name typed into a form."*
- **Run the loop** again → **RESOLVED**. Open **Patch**: its own `bre/…` branch, the pinned checkpoint, files changed *from git*.
  Open **Verification**: three levels; the test that was red is now green. Open **Ledger**: every prediction **confirmed** by a real run.

**3 · Scenario 1 again (≈60 s).** Create the same incident again → Run. *This time* the diagnosis comes from **memory, 0 tokens**.
Open **Diagnosis**: *"similarity 1.00 × ownership 0.42 = 0.42 ≥ τ 0.30"*. *"It didn't trust memory because it was similar. It trusted it because a passing test suite already vouched for it."* Approve, run, resolved.

**4 · The look-alike (≈90 s) — the moment that matters.** Create **"Connection pool exhaustion (LOOK-ALIKE)"** → Run → Approve → Run.
Memory answers (same symptom!) → the patch is applied → **the tests refute it** → **rolled back** → back to *AWAITING APPROVAL*, attempt 2.
Open **Ledger**: attempt 1's diagnosis is **refuted**; open **Diagnosis**: attempt 2's routing says *"already tried … failed verification"*.
Approve → Bob's full investigation finds the real cause (a cap in code) → **RESOLVED**.
*"The agent was wrong. The system found out because the test suite said so, undid the change, and stopped offering that memory."*

**5 · What BRE has learned (30 s).** The *What BRE has learned* tab: ownership per source and topic, computed **only** from verification-backed ledger rows.

**6 · Honesty (30 s).** *Evaluation* tab. *"On failures that recur, 6 of 10 diagnoses came from memory, none refuted, ~25% lower nominal cost. On a corpus with look-alike twins, the
tests refuted 4 of 13 reuses — each rolled back and re-investigated — and it still came out about 10% cheaper in nominal cost, with resolution identical. Token costs are nominal while Bob is simulated."*

## Live Bob (only after `verify_bob.py` exits 0)

```powershell
$env:BOB_API_KEY = "<key>"                       # not in a file, not on screen
$env:BRE_BOB_RECORD_DIR = "recordings"           # keep Bob's real output
.\scripts\run_demo.ps1 -Live
```
Expect the first live run to teach you something the stand-in could not. Keep the recordings.

## If something goes wrong

| Symptom | Cause | Fix |
|---|---|---|
| Run stops with **bob_unavailable** | Live mode requested, Bob Shell/key missing | Use `run_demo.ps1` (simulated) or finish `BOB_USAGE_PLAN.md` Task A |
| Run stops with **allowlist** | Repo not writable | Demo mode allowlists only its own workspace; for your own repo set `BRE_REPO_ALLOWLIST` |
| Run stops with **dirty_worktree** | Uncommitted tracked changes in the target | Commit/stash — BRE never mixes its patch with unsaved work |
| Approve says 401 | Wrong/missing operator key | The demo key is shown beside the button (public on purpose) |
| `NOT NULL constraint failed: approvals.approved_by` | Old `bre.db` from before S5 | Fixed automatically on startup (`rebuild_legacy_tables`); or delete `bre.db` |
| Port in use | Another instance | `-Port 8001` / `PORT=8001` |
| `python` can't `pip install` (SSL) | msys2 python on PATH | Use CPython 3.13 explicitly (README) |
