# Session Ledger — Index

One line per session, newest last. Append on close. See
[PROTOCOL.md](PROTOCOL.md) for the format and
[../stages/STAGES.md](../stages/STAGES.md) for where the build is.

**If you are new or returning:** read this bottom-up, then run `/catch-up`.

| # | Date | Title | Author | Stage | Status | The one thing to know |
|---|---|---|---|---|---|---|
| [0001](sessions/0001-asmos-alignment-and-workflow.md) | 2026-09-17 | ASMOS alignment + workflow | @dee | S0 | closed | ARCHITECTURE.md §8 describes ASMOS as a file-relevance ranker; the real ASMOS routes *agents* by verification-gated ownership. The doc understates the asset. |
| [0002](sessions/0002-environment-verified.md) | 2026-09-17 | Environment verified | @dee | S1 | closed | The default `python` here is msys2 and cannot install anything (no root CA store) — use CPython 3.13. Suite is green: 20 passed, 3 xfailed. |
| [0003](sessions/0003-evidence-collection-end-to-end.md) | 2026-09-26 | Evidence collection end to end | @opencode | S2 | closed | S2 is DONE: four read-only connectors + investigate endpoint return 9 evidence items across 5 source types; suite 40 passed, 3 xfailed. GitPython: stats.files is a dict, Diff.diff needs create_patch=True. |
| [0004](sessions/0004-outcome-ledger-and-harness.md) | 2026-09-26 | Outcome ledger and evaluation harness | @opencode | S3 | closed | S3 is DONE: ledger persists all three prediction types and verification closes them; 10-incident corpus runs 10/10 confirmed, deterministically. Suite 60 passed, 3 xfailed. `ledger.close()` returns the closed record — reading the pre-close object silently reports 0 confirmed. |
| [0005](sessions/0005-bob-interface-spike-and-adapter.md) | 2026-09-26 | Bob interface spike + read-only adapter | @opencode | S4 | closed | S4 is DONE: Bob = `bobide` (VS Code fork); interface = local WS JSON-RPC agent host, protocol recovered from shipped JS, round trip proven vs faithful fake. IBM publishes NO darwin server builds (404 vs linux 302) — live host needs linux/x64. Suite 72 passed, 3 xfailed. |
| [0006](sessions/0006-risk-engine-and-approval-gate.md) | 2026-09-26 | Risk engine + approval gate | @opencode | S5 | closed | S5 is DONE: deny-by-default gate at the transition entry point — no assessment ⇒ treated as CRITICAL; approvals carry API-key-resolved operator identity (body-supplied `approved_by` is ignored). Suite 84 passed, 3 xfailed. |

---

## Open threads across all sessions

Regenerate with:

```bash
grep -rn "Status:\*\* open" docs/memory/sessions/
```

| Session | Entry | Thread | Owner |
|---|---|---|---|
| 0001 | #8 | Ownership asymmetry in a real repo is assumed, not measured | unassigned |
| 0002 | #7 | `on_event` and `datetime.utcnow()` deprecations reproduce on 3.13; filtered, not fixed | unassigned |
| 0003 | #7 | S1 xfail gaps (missing incident FK, unset started_at, no DETECTED→CLOSED edge) remain | unassigned |
| 0004 | #2 | `eval:`-prefixed run ids close ledger records without a verification row — harden in S7 | S7 |
| 0005 | #1 | Live host cannot start on darwin (no REH build); chat-channel encoding + turn-completion delivery unconfirmed against the real host | first linux/x64 run |

Closed since last update: 0004#7 (token counts are zero until Bob lands) — closed by 0005#5. 0001#7 (Bob mechanism unverified) — closed by 0005#1 and 0005#7; its residual platform gap is tracked as 0005#1.

Closed since last update: 0001#10 (nothing runtime-verified) — closed by 0002#4 and 0002#5.
