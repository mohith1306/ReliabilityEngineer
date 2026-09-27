# Bob Reliability Engineer — team pack

**Read this first (5 minutes).** Everything a teammate needs to understand the project and finish the submission.

> **Deadline: Sunday 27 Sep 2026, 11:00 AM EDT = 20:30 IST.** Submit with a margin; do not attempt it in the last 10 minutes.
> IBM Bob 2.0 Hackathon on lablab.ai · <https://lablab.ai/ai-hackathons/ibm-bob-2-hackathon>

## Live links (GitHub)

| What | Where |
|---|---|
| Repository (public) | <https://github.com/mohith1306/ReliabilityEngineer> |
| **Submission tracker** (pinned — the one place to see status) | <https://github.com/mohith1306/ReliabilityEngineer/issues/3> |
| Main build (S6–S9, dashboard, submission pack) | **Merged** to `main`: <https://github.com/mohith1306/ReliabilityEngineer/pull/2> |
| **Demo fixes + this pack, awaiting review.** Merge before recording the video | <https://github.com/mohith1306/ReliabilityEngineer/pulls> (branch `demo-readiness`) |
| Task list with deadline | <https://github.com/mohith1306/ReliabilityEngineer/milestone/1> |

## What the project is, in three sentences

AI coding agents like IBM Bob can write a fix in minutes; teams then can't tell whether it was right, whether it was safe, or whether anyone learned anything.
**BRE (Bob Reliability Engineer) wraps Bob in a safety-and-learning loop**: gather evidence → Bob diagnoses (read-only) → score the risk → a human approves →
apply the fix on a git branch → the *real test suite* verifies it → roll back if it fails → remember which diagnoses turned out to be verifiably right.
BRE orchestrates Bob; it never reimplements it.

## The one thing everyone must know

> ### BRE has never made a call to a live IBM Bob.
> The code, tests, dashboard and demo are built and working (335 tests pass), but every "Bob" step in the demo is a **labelled stand-in**
> — the dashboard says **SIMULATED BOB** on every screen. Git checkpoints, branches, pytest verification, rollback, the approval gate and
> the ledger are all real; only the diagnosing/fixing agent is simulated.
>
> The judged criterion is *a clear application of IBM Bob*, and the rules require **Bob task-session screenshots from each team member**.
> Those can only be produced by people using Bob. **That is the critical path** → [02_TASKS_AND_ORDER.md](02_TASKS_AND_ORDER.md).

## Where things stand

| Stage | Status |
|---|---|
| S0 Alignment · S1 Foundation · S2 Evidence collection · S3 Outcome ledger · S5 Risk + approval gate | Done (teammate's work, now green on Windows) |
| S4 Bob adapter | **Blocked** — built and tested against documentation and fakes; needs a live call |
| S6 Write path · S7 Verification + bounded loop · S8 ASMOS routing · S9 Comparison | Done (this session) |
| Dashboard · demo mode · deploy scaffolding · submission drafts | Done — Dockerfile **never built** |

Numbers: 335 tests pass, 1 skipped (no Bob binary) — verified on **Windows only**. Results and their caveats: [RESULTS.md](../RESULTS.md).

## Five rules (they protect the submission)

1. **Never present a SIMULATED run as Bob's work.** The mode pill in the dashboard shows which it is.
2. **Never quote a token saving without "nominal"** unless the run was live and measured.
3. **Only claim Bob usage you can back with a file in the repo** (an artifact, a recording, a screenshot).
4. **Never commit `BOB_API_KEY`** or any secret. `.env` is gitignored; use `.env.example` as the template.
5. **Everything is public.** The repo is public and PR/issue text is visible to judges.

## Get it running (10 minutes)

**Windows** — use CPython, **not** the msys2 `python` (its pip can't verify SSL):
```powershell
git clone https://github.com/mohith1306/ReliabilityEngineer.git; cd ReliabilityEngineer
git checkout demo-readiness                         # until its PR is merged; then stay on main
"$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File scripts\run_demo.ps1   # open http://127.0.0.1:8000  (simulated Bob)
```
**macOS / Linux:**
```bash
git clone https://github.com/mohith1306/ReliabilityEngineer.git && cd ReliabilityEngineer
git checkout demo-readiness                         # until its PR is merged
python3 -m venv venv && venv/bin/pip install -r requirements.txt && scripts/run_demo.sh
```
No Bob or credentials are needed. In the dashboard: *Create demo incident → Run the loop → approve (the key is shown beside the button) → Run again*.
No browser? `python scripts/demo.py --twice`.

## What to do first, by role

| You are… | Start with |
|---|---|
| **Everyone** | Read [01_WHAT_WE_BUILT.md](01_WHAT_WE_BUILT.md); run the demo; do **Task C** (your own Bob screenshot — nobody can do it for you) |
| **Has Bob access** | Tasks A → B in [02_TASKS_AND_ORDER.md](02_TASKS_AND_ORDER.md) |
| **Has a hosting account** | Build/verify the Dockerfile and deploy (issue #9) |
| **Presenting / recording** | [03_PRESENTING_AND_JUDGE_QA.md](03_PRESENTING_AND_JUDGE_QA.md) and the [video script](../submission/VIDEO_SCRIPT.md) |
| **Will edit the code** | [04_HOW_TO_WORK_ON_THE_REPO.md](04_HOW_TO_WORK_ON_THE_REPO.md) |

## What's in this pack

- **`05_TEAM_DOSSIER.md` — the state of everything on one page: what is done (with evidence), what is not, demo-day risks, the GitHub issues reviewed, today's plan.** Read it second.
- `00`–`04` — the guides (this folder)
- `VIDEO_SCRIPT.md` — the 3-minute script. Every line has its reason, its source in the code, and how it was checked
- **Recording the video?** Open [demo_walkthrough.html](../submission/demo_walkthrough.html) (the script as a click-through page with a timer; works offline. With the demo running, open `http://127.0.0.1:8000/walkthrough` and switch to **Real dashboard** to run the actual demo beside the script) and read [recommendation.md](../submission/recommendation.md) (who says which part, and how to use the four photos)
- `reference/` — snapshot copies of the key project documents (live status, results, demo guide, all submission drafts, cover image, slides, ADRs, the session ledger entry). They are a **snapshot**: the repo is the source of truth, and `MANIFEST.txt` says which commit this was taken from.
- Regenerate the pack any time: `python scripts/make_team_pack.py`
