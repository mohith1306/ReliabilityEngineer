# Session Ledger — Index

One line per session, newest last. Append on close. See
[PROTOCOL.md](PROTOCOL.md) for the format and
[../stages/STAGES.md](../stages/STAGES.md) for where the build is.

**If you are new or returning:** read this bottom-up, then run `/catch-up`.

| # | Date | Title | Author | Stage | Status | The one thing to know |
|---|---|---|---|---|---|---|
| [0001](sessions/0001-asmos-alignment-and-workflow.md) | 2026-09-17 | ASMOS alignment + workflow | @dee | S0 | closed | ARCHITECTURE.md §8 describes ASMOS as a file-relevance ranker; the real ASMOS routes *agents* by verification-gated ownership. The doc understates the asset. |
| [0002](sessions/0002-environment-verified.md) | 2026-09-17 | Environment verified | @dee | S1 | closed | The default `python` here is msys2 and cannot install anything (no root CA store) — use CPython 3.13. Suite is green: 20 passed, 3 xfailed. |
| [0003](sessions/0003-bob-interface-confirmed.md) | 2026-09-17 | Bob interface documented | @dee | S4 | closed | Bob Shell `bob run --format json --mode ask\|plan\|agent` is exactly the surface BRE needs — and it reports its own tokens and cost. Adapter built; live call still needs an API key. |
| [0004](sessions/0004-asymmetry-measured.md) | 2026-09-19 | Asymmetry measured, premise refuted | @dee | S2 | closed | Ownership asymmetry in git history is **indistinguishable from chance** (NO-GO, 4/4 repos). Also: 0 reverts in 852 commits, so git has no refutation signal at all. Ownership must be learned from the outcome ledger. |

---

## Open threads across all sessions

Regenerate with:

```bash
grep -rn "Status:\*\* open" docs/memory/sessions/
```

| Session | Entry | Thread | Owner |
|---|---|---|---|
| 0001 | #7 | Bob adapter written but **never run against a live Bob** — needs Bob Shell + `BOB_API_KEY`. Close with `scripts/verify_bob.py` | unassigned |
| 0001 | #8 | Ownership asymmetry in a real repo is assumed, not measured | unassigned |
| 0002 | #7 | `on_event` and `datetime.utcnow()` deprecations reproduce on 3.13; filtered, not fixed | unassigned |
| 0003 | #11 | Campus network may have a TLS interception proxy — could break the Bob Shell install | unassigned |
| 0004 | #9 | Asymmetry test has almost no power at 1–4 agents; a 50+ contributor repo is the decisive follow-up, not run | unassigned |

Closed since last update: **0001#8 (ownership asymmetry unmeasured) — closed by 0004#4 with a
negative result.** Earlier: 0001#10 (nothing runtime-verified) — closed by 0002#4 and 0002#5.

Note on 0001#7: it narrowed but did not close. The *interface* is documented (0003#2) and
the adapter is built and tested (0003#8); what remains is confirming the documented
contract against a running Bob.
