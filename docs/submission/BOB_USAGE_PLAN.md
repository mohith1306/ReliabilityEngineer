# IBM Bob usage — the part only a person can do

The hackathon requires a **clear application of IBM Bob 2.0**, an **IBM Bob usage statement**, the
repository files **where Bob assisted**, and **Bob task-session summary screenshots from each team member**.
Access is time-limited and usage-limited. None of this can be generated, faked, or done by an agent
on your behalf — and it must not be: the judges can see the task summaries.

## The honest starting point

Be precise about this in the submission, because a wrong claim here costs more than a thin one:

| Question | Answer today |
|---|---|
| Has BRE ever made a real call to IBM Bob? | **No.** Bob Shell is not installed on the Windows machine and `BOB_API_KEY` has never been set. `python scripts/verify_bob.py` exits 2 with instructions. |
| What proves the Bob integration works? | Documentation-derived contract tests (`tests/unit/test_bob_shell.py`) and a fake agent-host (`tests/support/fake_bob_host.py`). **Not** a live call. |
| What wrote this repository's code? | Claude Code and opencode (an AI agent on the teammate's Mac), per the session ledger. **Not** IBM Bob. |
| What does the demo show? | A *labelled* replay stand-in for Bob. The dashboard says **SIMULATED BOB** on every screen. |

So the plan below turns "BRE is designed to orchestrate Bob" into "Bob was actually used, on this codebase, by
each of us, and here is the evidence." Do them **in this order** — each unblocks the next.

## Task A — close the live-Bob thread (≈15 min, one person, Windows or macOS) · REQUIRED

Proves the interface. Closes thread `0001#7`, the project's largest open risk.

```powershell
# Windows (needs Node.js 24+)
irm -Uri https://bob.ibm.com/download/bobshell.ps1 | iex
$env:BOB_API_KEY = "<key with Scope=Inference from the Bob web portal>"   # never commit it, never paste it in a prompt
bob --version
venv\Scripts\python.exe scripts\verify_bob.py
```
```bash
# macOS / Linux
curl -fsSL https://bob.ibm.com/download/bobshell.sh | bash
export BOB_API_KEY="<key>"
python scripts/verify_bob.py
```

- **Exit 0** writes `docs/artifacts/bob_roundtrip_<stamp>.json` (tokens, cost, task id). **Commit that file.**
- **Screenshot:** the terminal showing `THREAD 0001#7 CLOSED`, and the Bob task summary.
- If the output schema differs from the documented one, `tests/unit/test_bob_shell.py::test_parses_documented_stats_block`
  is where it will show. **Log that as a finding in the session ledger, even if it embarrasses the docs.**
- If the install fails with a certificate error, see thread `0007#11` (possible TLS-intercepting proxy on the campus network).

## Task B — one real end-to-end run with live Bob, recorded (≈20 min) · REQUIRED for the video

Shows Bob doing the diagnosis and the fix inside BRE's gates, on a real failing repository.

```powershell
$env:BRE_BOB_RECORD_DIR = "recordings"          # keeps Bob's real prompts/replies/usage (see bob/recording.py)
Remove-Item Env:BRE_BOB_TRANSPORT -ErrorAction SilentlyContinue   # NOT replay
venv\Scripts\python.exe scripts\demo.py --live --scenario seeded_failure
```

Or in the dashboard: `.\scripts\run_demo.ps1 -Live`, create the incident, run the loop, approve, run again.

- Bob's diagnosis is read-only (`ask` mode); Bob edits files only in the remediation step (`agent` mode) and only after approval.
- **Expect surprises.** The replay stand-in was written to match the documented output; real Bob may phrase its JSON differently
  (`DiagnosisParseError`) or behave differently in agent mode. Whatever happens is the most useful thing the team will learn all day.
- Commit `recordings/*.json` (they contain the prompts, which include the fixture's code — nothing secret). These are Bob's real
  outputs and can be replayed later when the allowance runs out.
- **Screenshot:** the dashboard/terminal with the mode pill reading **LIVE IBM BOB**, plus the Bob task summary.

## Task C — Bob reviews BRE's own safety design (≈20 min, EACH team member) · REQUIRED for the screenshots

Every team member needs their own Bob task summary. This one is cheap and genuinely useful: ask Bob to attack the write path.

In **IBM Bob (IDE), Ask or Plan mode**, opened on this repository, paste:

> Review `reliability/remediation/engine.py`, `reliability/remediation/git_ops.py` and `reliability/remediation/guards.py`.
> They are the only code allowed to modify a target repository. Find any way a remediation could (1) write to the
> target's default branch, (2) skip the approval gate or the allowlist, (3) leave the repo half-modified after a failure,
> or (4) make the tests pass by weakening them without `guards.check_patch` noticing. Give file:line references and a
> concrete failing scenario for each finding. Do not modify any files.

- Save Bob's answer to `docs/submission/bob_review_<yourname>.md` (verbatim, plus one line saying what you did with each finding).
- **Every finding you agree with becomes a failing test first, then a fix.** That is the "code where Bob assisted".
- **Screenshot:** the completed Bob task summary.

## Task D — Bob Code mode adds a scenario (≈30 min, at least one member) · STRONG

Real Bob-authored code in the repo, with tests that check it.

In **Bob (IDE), Code mode**:

> Add a fourth seeded failure scenario to this repository, following exactly how `tests/fixtures/auth_timeout/` and
> `bob/cassettes/auth_timeout.json` are built: a tiny Python service in `tests/fixtures/<name>/` whose test reads a
> config value and fails because of a regression, a `ci/failure.log`, a story entry in
> `reliability/evaluation/fixtures.py`, a cassette in `bob/cassettes/`, and a corpus spec `tests/e2e/corpus/seed-015.json`.
> Choose a failure mode not already covered (for example a retry count of 0, or a cache TTL of 0). Do not modify existing files
> except `reliability/evaluation/fixtures.py`. Then run `venv\Scripts\python.exe -m pytest tests/e2e -q` and fix anything that fails.

- Review the diff yourself before committing; the guards and tests are the safety net, not a substitute for reading it.
- **Screenshot:** the Bob task summary and the green `pytest` run.

## What to screenshot (checklist per team member)

- [ ] Bob **task session summary** for Task C (everyone) — and Tasks A/B/D for whoever ran them
- [ ] The terminal or dashboard showing **LIVE IBM BOB** (Task B)
- [ ] `git log --oneline` showing the commit(s) that contain Bob-assisted files
- [ ] Put them in `docs/submission/screenshots/<name>/` and reference them from the submission form

## Then fill in the usage statement

`docs/submission/SUBMISSION.md` has the statement with `[TEAM: …]` markers. Replace each marker with what
**actually happened**, including anything that failed. Delete any sentence you cannot back with an artifact in this repo.
