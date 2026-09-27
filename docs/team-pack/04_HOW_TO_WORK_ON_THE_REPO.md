# Working on the repository

## The working agreement (short form)

The full version is [CLAUDE.md](../../CLAUDE.md) — read it if you (or an agent you use) will change code.

- **Every working session writes a numbered memory file** under `docs/memory/sessions/`. The people and agents on this project lose their context at the end of every session; the ledger is the memory. Format: [PROTOCOL.md](../memory/PROTOCOL.md).
- **Every claim carries evidence** — a `file:line`, command output or artifact path, or the words `none (hypothesis)`.
- **Stages have verifiable exit criteria** in [STAGES.md](../stages/STAGES.md); never mark one DONE without naming the evidence.
- **Architectural non-negotiables** (breaking one needs an ADR): Bob is orchestrated, not reimplemented · reputation moves only on verification · every computed score stores its components · every prediction gets an outcome record · **no write path without a passed approval gate** · the reliability loop must terminate.

## Git workflow

```bash
git fetch origin
git checkout -b my-change origin/main          # branch off main; never commit to main directly
# ...work, run the tests...
git push -u origin my-change
gh pr create --base main                        # then ask a teammate to review
```
- Claim a session number without colliding: `ls docs/memory/sessions | tail -1`; if two people pick the same number, the later pusher renames (PROTOCOL.md).
- **Do not commit** `bre.db`, `.env`, anything under `runs/`, or `recordings/` that contain anything you don't want public.
- Line endings: the repo is LF everywhere (`.gitattributes`). If a diff of a 5-line change shows hundreds of lines, your editor wrote CRLF — check `git diff --stat` before committing.

## Commands

```powershell
venv\Scripts\python.exe -m pytest                         # the whole suite (~5 min; real git + real pytest inside)
venv\Scripts\python.exe -m pytest tests/unit -q           # fast subset
venv\Scripts\python.exe scripts\cockpit.py                # one-screen status + 15 integrity checks
venv\Scripts\python.exe scripts\cockpit.py --tests --write   # also run the suite and refresh docs/STATUS.md
venv\Scripts\python.exe scripts\demo.py --twice           # terminal walkthrough
.\scripts\run_demo.ps1                                    # dashboard (add -Live for real Bob)
venv\Scripts\python.exe -m reliability.evaluation.compare --orderings 3     # Bob alone vs BRE
venv\Scripts\python.exe scripts\tune_tau.py --slice full --latest           # tune the routing threshold
venv\Scripts\python.exe scripts\build_results.py          # regenerate docs/RESULTS.md from the artifacts
python scripts/make_team_pack.py                          # rebuild this pack + the zip
```
Claude Code users: `/cockpit`, `/catch-up`, `/session-start`, `/session-log`, `/session-end`, `/stage`.

## Environment gotchas (each of these cost real time)

| Gotcha | What to do |
|---|---|
| **msys2 `python` on PATH** (Windows) — its pip can't verify SSL, and it builds a POSIX-layout venv | Use CPython explicitly: `%LOCALAPPDATA%\Programs\Python\Python313\python.exe -m venv venv` |
| `pytest.ini` already passes `-q`; another `-q` (`-qq`) **drops the summary line** | Don't add `-q` when you need the counts |
| An old `bre.db` from before S5 has `approvals.approved_by NOT NULL` | Fixed automatically on startup (`rebuild_legacy_tables`); or delete `bre.db` |
| Windows editors / tools that write **CRLF** | `.gitattributes` normalizes on commit; still check `git diff --stat` |
| Running `git` in a target repo from Python on Windows can leave file handles open | `connectors/git.py` closes its `Repo` objects; keep doing that |

## Map of the repository

```
apps/api/        FastAPI: incidents, the loop (/advance, /detail), approvals, risk, ownership, results, demo
apps/web/        The dashboard (one file, no CDN)
reliability/     investigator · risk · remediation (THE write path) · verification · ledger · orchestration (lifecycle, loop, routed) · evaluation
asmos_bridge/    ownership · routing (router, simulate, tuning) · verified memory · consolidation — pinned to real ASMOS by parity tests
bob/             shell.py (documented `bob run`) · transport.py · execution.py (agent host, experimental) · replay.py + cassettes/ · recording.py
connectors/      repository · git · tests · ci (read-only); git_history.py for ownership analysis
models/          Pydantic domain models
tests/           unit · integration · e2e — real git repos, real pytest
scripts/         cockpit · demo · run_demo.* · tune_tau · validate_simulator · build_results · make_pitch · make_cover · make_team_pack · verify_bob
docs/            ARCHITECTURE (+ ERRATA) · decisions (ADRs) · memory (session ledger) · stages · submission · team-pack · DEMO · RESULTS · STATUS
```

## Where to read the reasoning

| Question | Read |
|---|---|
| What happened last session, entry by entry | [session 0009](../memory/sessions/0009-reconcile-and-build-s6-s9.md) |
| Where the build is | [STATUS.md](../STATUS.md) (generated) and [STAGES.md](../stages/STAGES.md) |
| Why is Bob simulated / why two Bob adapters | [ADR-0005](../decisions/ADR-0005-bob-surfaces-and-replay.md) |
| Why is τ tuned this way (and what we got wrong) | [ADR-0006](../decisions/ADR-0006-routing-sources-and-tau.md) |
| What the old architecture doc gets wrong | [ERRATA.md](../architecture/ERRATA.md) — read before trusting `ARCHITECTURE.md` |
| Open problems | the "Open threads" table in [INDEX.md](../memory/INDEX.md) |
