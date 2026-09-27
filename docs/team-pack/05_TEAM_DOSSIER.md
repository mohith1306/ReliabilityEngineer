# Team dossier — state of the project, 27 Sep 2026 (morning, IST)

One page to read after [00_START_HERE.md](00_START_HERE.md). It says what is finished (with the evidence), what is not, what can go wrong on
demo day, where every GitHub issue stands, and the plan for the day. **Deadline: 20:30 IST today (11:00 AM EDT). Aim to submit by 19:30.**

---

## 1 · Bottom line

1. **The software is finished and working.** The whole loop runs in the dashboard, the test suite is green (335 passed, 1 skipped), and the video
   flow was performed click by click this morning.
2. **Nothing has yet been done with a live IBM Bob.** That is the gap between us and a strong submission: the judged criterion is
   *a clear application of IBM Bob*, and the rules require **Bob task-session screenshots from every member**. Only people can do this.
3. **Merge the `demo-readiness` PR first.** On `main` right now, the dashboard's **Approve** button fails in a browser (details in §3).
4. **Nobody is assigned to any GitHub issue.** Put names on #5, #6, #7, #9, #10 and #11 in the first 15 minutes of the day.

---

## 2 · What is done — with evidence

| Area | What exists | Evidence |
|---|---|---|
| The loop | Detect → Investigate → Diagnose → Assess risk → Approve → Remediate → Verify → Learn; capped at 3 attempts | `reliability/orchestration/loop.py`; `tests/e2e/test_reliability_loop.py` |
| Write-path safety | Allowlist, pinned git checkpoint, `bre/<incident>/attempt-<n>` branch only, changed files from `git diff`, diff guard (5 rules), exact rollback, one `allow_writes=True` in the codebase | `reliability/remediation/`; `tests/integration/test_remediation.py` |
| Approval | Identity from an API key; a forged name in the request body is ignored; the gate is re-checked inside the write engine | `apps/api/routes/approvals.py:50`; `reliability/remediation/engine.py:116`; `test_full_lifecycle_over_http_with_an_authenticated_human_approval` |
| Verification | The failing test, then its whole file, then the entire suite; zero tests collected never counts as a pass | `reliability/verification/verifier.py:103-176` |
| Outcome ledger | Every prediction written as pending; closed only by a verification run | `reliability/ledger/record.py:101,168`; ADR-0003 |
| ASMOS routing | Trust / ownership / routing math pinned to the real ASMOS code | 95 parity tests in `tests/unit/test_asmos_parity.py` (ASMOS commit `ee072ea162`) |
| Measured results | Bob-alone vs BRE vs frozen ablation, 3 slices × 3 orderings; τ tuner validated 9/9 against measured runs | `docs/RESULTS.md`; `docs/artifacts/`; ADR-0006 |
| Dashboard + demo mode | One-page UI, three scenarios, Reset, the SIMULATED BOB label on every screen | `apps/web/index.html`; `apps/api/routes/demo.py`; `tests/integration/test_api_loop.py` |
| Submission drafts | Form text, Bob-usage plan, checklist, 12-slide deck, cover image, **annotated video script** | `docs/submission/` |
| GitHub tracking | Pinned tracker, milestone with the deadline, one issue per remaining task | [#3](https://github.com/mohith1306/ReliabilityEngineer/issues/3), milestone 1 |
| This pack | Guides 00–05, the video script, a reference snapshot, and a manifest with a sha256 per file | `python scripts/make_team_pack.py`; `tests/unit/test_team_pack.py` |

**Verified on Windows only.** Nobody has run the suite on macOS or Linux yet (#12), and nobody has built the Docker image (#9).

---

## 3 · Demo-day inspection — what can go wrong, and what was done about it

Method: the video script was **performed** in the dashboard (all three incidents, every tab), and every launcher, deploy file and GitHub
issue was read for anything that would break on the day. **FIXED** = changed on branch `demo-readiness`, with a test.

| # | Risk | Likelihood · impact | Status | What to do |
|---|---|---|---|---|
| R1 | **Approve fails in the browser** with `[object Object]`. The dashboard dropped `Content-Type` on the one call that sends a key, so the server returned a 422 | Certain on `main` · blocks the demo | **FIXED** (`apps/web/index.html`; regression test) | Merge `demo-readiness` before recording |
| R2 | A browser that cached the old page keeps running the bug even after the fix | Likely · looks like R1 | **FIXED** (page served `no-cache`, tested) | Ctrl+F5 once anyway |
| R3 | On the look-alike, the Patch tab's summary said "Restore … to 20" over a `20 → 200` diff. That contradiction would be on camera | Certain · credibility | **FIXED** (the stand-in matches whole tokens; the patch is labelled *applied to a repository it does not fit*; tested). Measured results unchanged | — |
| R4 | `docker build` would copy a local `.env` (possibly holding `BOB_API_KEY`) into the image | Possible · leaks a secret | **FIXED** (`.dockerignore` excludes `.env*`, `recordings`, `dist`) | Never build from a folder with real keys you don't need |
| R5 | The look-alike only shows the refutation if incident 1 was resolved **first, since the last Reset** | Likely under pressure · kills the best moment | Mitigated (pre-flight in VIDEO_SCRIPT) | Reset → 1 → 2 → 3, in order |
| R6 | `bre.db` keeps incidents and memory across restarts, so old state changes the story | Likely · confusing numbers | Mitigated (Reset button) | Reset before every take |
| R7 | Windows: `.\scripts\run_demo.ps1` → "running scripts is disabled on this system" | Likely on a fresh laptop | Mitigated (docs use `powershell -ExecutionPolicy Bypass -File …`) | Use that form |
| R8 | With no `venv`, `run_demo.ps1` falls back to whatever `python` is on PATH (msys2 on some machines: SSL and venv problems) | Possible | Open (documented) | Create the venv with CPython, per 00_START_HERE |
| R9 | **Live Bob has never been called.** Bob Shell's real JSON, modes or exit codes may differ from the documentation the adapter was built from | Unknown · blocks Task B | **Open, critical path** | Do Task A (#5) first thing; if it fails, record SIMULATED and say so. Never mix a live start with a simulated finish |
| R10 | **Docker image never built**; Render's free plan sleeps (the first request after idle can take ~a minute); storage is ephemeral; a public demo lets any visitor create repos on the server | Possible · a judge sees a spinner | Open (#9) | Build locally first; open the URL yourself just before submitting and again before judging; Reset is the recovery |
| R11 | Double-clicking **Run the loop** | Likely · harmless | OK: second click gets "already being advanced" (HTTP 409), `apps/api/routes/loop.py:55-57` | Wait for *Working…* |
| R12 | A live-Bob error mid-demo | Possible | OK: shown as a readable message (HTTP 503), `loop.py:63-64` | Switch to a SIMULATED take |
| R13 | Saying "Bob fixed it" or "saves 25%" over a simulated run | Possible · credibility | Mitigated (script wording, rules in 00/03) | Say "the agent" and "nominal" |
| R14 | Tracker issues linked to the old branch, so teammates would read a stale script | Certain | Fixed on GitHub (links now point at `main`) | — |
| R15 | Submitting with a `[TEAM: …]` marker still in the text (12 in `SUBMISSION.md`) | Possible under time pressure | Open (#11) | Search for `[TEAM` before pressing submit |

Not a demo risk, but know it: `datetime.utcnow()` is still used in a few places (deprecated; ERRATA §B). The warning is filtered in `pytest.ini`.

---

## 4 · GitHub issues — reviewed one by one

All 11 open issues were read this morning. **None has an assignee or a comment.** That is the main organisational risk: the tasks are clear, but nobody owns them.

| Issue | State | Finding | Recommended action |
|---|---|---|---|
| [#3](https://github.com/mohith1306/ReliabilityEngineer/issues/3) Tracker | Open, pinned | Links pointed at the old branch; the #4 box was unticked though PR #2 had merged | Updated. Keep ticking boxes as tasks close |
| [#4](https://github.com/mohith1306/ReliabilityEngineer/issues/4) Merge PR #2 | **Done** | PR #2 was merged 2026-09-26 22:18 UTC (commit `cdcdd33`) | Closed with a comment pointing at the `demo-readiness` PR, which is the new "merge first" item |
| [#5](https://github.com/mohith1306/ReliabilityEngineer/issues/5) Task A — Bob Shell round trip | Open | The single most important task: #6, the Bob usage statement and the credibility of the video depend on it | **Assign first.** Needs Node 24+ and a Bob API key. ~15 min |
| [#6](https://github.com/mohith1306/ReliabilityEngineer/issues/6) Task B — live run | Open | Depends on #5. Expect differences from the documented schema; write them down, they are findings | Assign with #5 |
| [#7](https://github.com/mohith1306/ReliabilityEngineer/issues/7) Task C — each member | Open | **A submission rule**: every member needs their own Bob screenshot. Nobody can do it for anyone else | Every member, before lunch |
| [#8](https://github.com/mohith1306/ReliabilityEngineer/issues/8) Task D — 4th scenario | Open | Nice-to-have: the strongest "code where Bob assisted" evidence, but not required | Only if #5–#7 are done by ~12:30 |
| [#9](https://github.com/mohith1306/ReliabilityEngineer/issues/9) Docker + URL | Open | Image never built. `.dockerignore` gap fixed (R4). Git identity is already handled (`git_ops.py:31`), so that suspect from the issue is ruled out | Assign someone with Docker Desktop + a Render account |
| [#10](https://github.com/mohith1306/ReliabilityEngineer/issues/10) Video | Open | Script is now annotated and checked. The Approve bug (R1) would have broken the recording on `main` | Record after merging `demo-readiness` |
| [#11](https://github.com/mohith1306/ReliabilityEngineer/issues/11) Finalize + submit | Open | 12 `[TEAM:]` markers in `SUBMISSION.md`; the slide 4 TEAM box; screenshots | One owner; submit by 19:30 |
| [#12](https://github.com/mohith1306/ReliabilityEngineer/issues/12) macOS/Linux run | Open | Only Windows is verified. A green run on a Mac is cheap insurance | Whoever has a Mac, 10 min |
| [#13](https://github.com/mohith1306/ReliabilityEngineer/issues/13) Backlog | Open | Post-hackathon; correctly not on the critical path | Leave |

---

## 5 · The plan for today (IST)

| When | What | Who |
|---|---|---|
| 08:30–09:00 | Read this dossier. **Assign every issue.** Review + merge the `demo-readiness` PR | lead |
| 09:00–09:30 | **Task A (#5)**: Bob Shell + `scripts/verify_bob.py` | Bob-access person |
| 09:00–12:00 | **Task C (#7)**: each member's Bob review + screenshot | everyone |
| 09:30–10:30 | **Task B (#6)**: one live run, recorded (`BRE_BOB_RECORD_DIR=recordings`) | Bob-access person |
| 10:30–12:30 | Task D (#8) if time allows · macOS run (#12) | volunteer |
| 12:00–14:00 | **Docker + deploy + URL (#9)** | hosting person |
| 14:00–16:30 | **Record the video (#10)**, following VIDEO_SCRIPT.md exactly | presenter |
| 16:30–19:00 | Fill `[TEAM:]` markers, slides → PDF, final read (#11) | everyone |
| **19:30** | **Submit.** One hour of margin before 20:30 | lead |

**If Bob access fails:** do not fake anything. Submit the SIMULATED version, say plainly that the live integration is implemented and tested
against the documented contract but not yet exercised, and show whatever Bob screenshots you have. A thinner, truthful submission survives Q&A;
a claim a judge can disprove does not.

---

## 6 · Where to look

| Need | File |
|---|---|
| Record the video | [VIDEO_SCRIPT.md](../submission/VIDEO_SCRIPT.md), with a reason and a source on every line |
| Answer a judge | [03_PRESENTING_AND_JUDGE_QA.md](03_PRESENTING_AND_JUDGE_QA.md) |
| Exact steps for Tasks A–D | [02_TASKS_AND_ORDER.md](02_TASKS_AND_ORDER.md) |
| Numbers and their caveats | [RESULTS.md](../RESULTS.md) |
| Why a decision was made | [the ADRs](../decisions/) and [session 0010](../memory/sessions/0010-demo-readiness-and-team-pack.md) |
