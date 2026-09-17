# Session Ledger — Index

One line per session, newest last. Append on close. See
[PROTOCOL.md](PROTOCOL.md) for the format and
[../stages/STAGES.md](../stages/STAGES.md) for where the build is.

**If you are new or returning:** read this bottom-up, then run `/catch-up`.

| # | Date | Title | Author | Stage | Status | The one thing to know |
|---|---|---|---|---|---|---|
| [0001](sessions/0001-asmos-alignment-and-workflow.md) | 2026-09-17 | ASMOS alignment + workflow | @dee | S0 | closed | ARCHITECTURE.md §8 describes ASMOS as a file-relevance ranker; the real ASMOS routes *agents* by verification-gated ownership. The doc understates the asset. |
| [0002](sessions/0002-environment-verified.md) | 2026-09-17 | Environment verified | @dee | S1 | closed | The default `python` here is msys2 and cannot install anything (no root CA store) — use CPython 3.13. Suite is green: 20 passed, 3 xfailed. |

---

## Open threads across all sessions

Regenerate with:

```bash
grep -rn "Status:\*\* open" docs/memory/sessions/
```

| Session | Entry | Thread | Owner |
|---|---|---|---|
| 0001 | #7 | Bob integration mechanism is unverified — no confirmed programmatic interface | unassigned |
| 0001 | #8 | Ownership asymmetry in a real repo is assumed, not measured | unassigned |
| 0002 | #7 | `on_event` and `datetime.utcnow()` deprecations reproduce on 3.13; filtered, not fixed | unassigned |

Closed since last update: 0001#10 (nothing runtime-verified) — closed by 0002#4 and 0002#5.
