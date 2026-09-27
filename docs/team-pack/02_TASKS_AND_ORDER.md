# Tasks, order and owners

Only people can do these (credentials, cameras, accounts, and the rule that **each member needs their own Bob screenshot**).
Live status is on the pinned tracker: <https://github.com/mohith1306/ReliabilityEngineer/issues/3>. Each row below is a GitHub issue with the exact steps.

**Deadline: Sun 27 Sep 2026, 11:00 AM EDT = 20:30 IST.** Suggested plan (IST) — adjust freely, but keep the order:

| Window (IST) | Task | Issue | Owner (write a name) | Needs | Time |
|---|---|---|---|---|---|
| 08:30–09:00 | Review and **merge the `demo-readiness` PR** (demo bug fixes + this pack; PR #2 is already merged). The macOS teammate runs `pytest` and comments the result | [pulls](https://github.com/mohith1306/ReliabilityEngineer/pulls), [#12](https://github.com/mohith1306/ReliabilityEngineer/issues/12) | ____________ | merge rights; a Mac | 30 min |
| 09:00–09:30 | **Task A** — install Bob Shell, run `scripts/verify_bob.py` | [#5](https://github.com/mohith1306/ReliabilityEngineer/issues/5) | ____________ | Node 24+, Bob API key | 15 min |
| 09:30–10:30 | **Task B** — one live end-to-end run with Bob, recorded | [#6](https://github.com/mohith1306/ReliabilityEngineer/issues/6) | ____________ | Task A done | 20 min |
| 09:00–12:00 | **Task C** — *each member*: Bob reviews the write path; save answer + screenshot | [#7](https://github.com/mohith1306/ReliabilityEngineer/issues/7) | **every member** | Bob IDE access | 20 min each |
| 10:30–12:30 | **Task D** — Bob (Code mode) authors a 4th scenario | [#8](https://github.com/mohith1306/ReliabilityEngineer/issues/8) | ____________ | Bob IDE access | 30 min |
| 12:00–14:00 | **Build the Dockerfile, deploy, get the URL** | [#9](https://github.com/mohith1306/ReliabilityEngineer/issues/9) | ____________ | Docker + hosting account | 45 min |
| 14:00–16:30 | **Record the demo video** (ideally the live run from Task B) | [#10](https://github.com/mohith1306/ReliabilityEngineer/issues/10) | ____________ | screen recorder | 1–2 h |
| 16:30–19:00 | **Finalize the text, review slides, fill every `[TEAM:]` marker** | [#11](https://github.com/mohith1306/ReliabilityEngineer/issues/11) | ____________ | everyone | 1–2 h |
| **by 19:30** | **Submit on lablab.ai** (one hour of margin) | [#11](https://github.com/mohith1306/ReliabilityEngineer/issues/11) | ____________ | | |

If Bob access turns out to be slow or impossible, **do not fake anything**: submit what is true (the stand-in is labelled everywhere) and say plainly that live Bob integration
is implemented but not yet exercised. A truthful, thinner submission beats one a judge can disprove.

## Task A — install Bob Shell and run the round-trip check (≈15 min)

```powershell
# Windows (needs Node.js 24+)
irm -Uri https://bob.ibm.com/download/bobshell.ps1 | iex
$env:BOB_API_KEY = "<key with Scope=Inference from the Bob web portal>"    # never commit it, never paste it in a prompt
bob --version
venv\Scripts\python.exe scripts\verify_bob.py
```
```bash
# macOS / Linux
curl -fsSL https://bob.ibm.com/download/bobshell.sh | bash
export BOB_API_KEY="<key>"
python scripts/verify_bob.py
```
Exit **0** writes `docs/artifacts/bob_roundtrip_<stamp>.json` → **commit it**. If Bob's real output differs from the documented schema, that is a finding — write it in the ledger.
Install fails with a certificate error? See thread 0007#11 (possible TLS-intercepting campus proxy). Screenshot the terminal and the Bob task summary.

## Task B — one live run, recorded (≈20 min)

```powershell
$env:BRE_BOB_RECORD_DIR = "recordings"
Remove-Item Env:BRE_BOB_TRANSPORT -ErrorAction SilentlyContinue        # must NOT be "replay"
venv\Scripts\python.exe scripts\demo.py --live --scenario seeded_failure
```
or `.\scripts\run_demo.ps1 -Live` and use the dashboard. Success looks like: the pill says **LIVE IBM BOB**, Bob's diagnosis appears, you approve, Bob edits a `bre/…` branch, the tests pass, `recordings/*.json` exist. Expect surprises (Bob may format its JSON differently or behave differently in agent mode) — write down anything that differs from the documentation.

## Task C — EACH member: Bob reviews the write path (≈20 min each)

In **IBM Bob (IDE), Ask or Plan mode**, opened on this repo, paste:

> Review `reliability/remediation/engine.py`, `reliability/remediation/git_ops.py` and `reliability/remediation/guards.py`. They are the only code allowed to modify a target repository. Find any way a remediation could (1) write to the target's default branch, (2) skip the approval gate or the allowlist, (3) leave the repo half-modified after a failure, or (4) make the tests pass by weakening them without `guards.check_patch` noticing. Give file:line references and a concrete failing scenario for each finding. Do not modify any files.

Save Bob's answer verbatim to `docs/submission/bob_review_<yourname>.md` with one line per finding saying what you did about it. Every finding you agree with becomes a **failing test first, then a fix** — that's the "code where Bob assisted". Put your screenshot of the Bob task summary in `docs/submission/screenshots/<yourname>/`.

## Task D — Bob (Code mode) adds a scenario (≈30 min, at least one member)

> Add a fourth seeded failure scenario to this repository, following exactly how `tests/fixtures/auth_timeout/` and `bob/cassettes/auth_timeout.json` are built: a tiny Python service in `tests/fixtures/<name>/` whose test reads a config value and fails because of a regression, a `ci/failure.log`, a story entry in `reliability/evaluation/fixtures.py`, a cassette in `bob/cassettes/`, and a corpus spec `tests/e2e/corpus/seed-015.json`. Choose a failure mode not already covered (for example a retry count of 0, or a cache TTL of 0). Do not modify existing files except `reliability/evaluation/fixtures.py`. Then run `venv\Scripts\python.exe -m pytest tests/e2e -q` and fix anything that fails.

Read the diff yourself before committing; the tests and guards are the safety net, not a substitute.

## The submission fields that need a person

| Field | What's needed |
|---|---|
| Bob task-session screenshots (each member) | Tasks A–D; put in `docs/submission/screenshots/<name>/` |
| Demo application platform + URL | Deploy (issue #9); the hosted demo is simulated-Bob by design |
| Video | Record (issue #10); say LIVE or SIMULATED in the first 15 seconds |
| IBM Bob usage statement | Replace every `[TEAM: …]` marker in [SUBMISSION.md](../submission/SUBMISSION.md) §4 with what actually happened |
| Slides | Update the yellow TEAM box on slide 4 in `docs/submission/BRE_pitch.html`; Ctrl+P → Save as PDF (landscape, margins none, background graphics on) |

Full detail for all of this: [BOB_USAGE_PLAN.md](../submission/BOB_USAGE_PLAN.md), [CHECKLIST.md](../submission/CHECKLIST.md), [SUBMISSION.md](../submission/SUBMISSION.md).
