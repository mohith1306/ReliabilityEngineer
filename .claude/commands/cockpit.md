---
description: One-screen ground truth — git, stages, tests, submission checklist, integrity checks
argument-hint: [--tests] [--write]
allowed-tools: Bash, Read
---

Run the project cockpit and interpret it. Use this at the **start** of a session (before
`/catch-up`, which supplies the *why*) and again before `/session-end`.

```bash
venv/Scripts/python.exe scripts/cockpit.py $ARGUMENTS
```

(Use `venv/bin/python` on macOS/Linux. Add `--tests` to re-run the suite and record the
result; add `--write` to refresh `docs/STATUS.md`.)

Then report, in at most 10 lines:

1. **Clock** — time remaining to the deadline.
2. **Branch health** — is `origin/main` contained in this branch? unpushed work? merge half-done?
3. **Tests** — green or red, and whether the recorded run is stale.
4. **Integrity** — every failing check, verbatim. A failing integrity check outranks feature work.
5. **Next** — the cockpit's NEXT list, reordered by your own judgement if it is wrong, and say so.

The cockpit reads ground truth; it does not decide. If it disagrees with a session file, trust
the cockpit for *state* and the session file for *reasoning*, and log the discrepancy.
