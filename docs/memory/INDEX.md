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
| [0007](sessions/0007-bob-interface-confirmed.md) | 2026-09-17 | Bob interface documented | @dee | S4 | closed | Bob Shell `bob run --format json --mode ask\|plan\|agent` is the *officially documented* non-interactive surface, and it reports its own tokens and cost. Adapter built against the docs; **never run against a live Bob** — needs an install and `BOB_API_KEY`. *(Renumbered from 0003 on reconcile.)* |
| [0008](sessions/0008-asymmetry-measured.md) | 2026-09-19 | Asymmetry measured, premise refuted | @dee | S2 | closed | Ownership asymmetry in git history is **indistinguishable from chance** (NO-GO, 4/4 repos), and 852 commits contain 0 reverts, so git has no refutation signal. Ownership must be learned from the outcome ledger. *(Renumbered from 0004 on reconcile.)* |
| [0009](sessions/0009-reconcile-and-build-s6-s9.md) | 2026-09-27 | Reconcile two lines, build S6–S9 | @dee + Claude | S6–S9 | closed | The team's S2–S5 was already on `main`; this branch had diverged. Reconciled, fixed Windows, built the write path, verification loop, ASMOS routing and a comparison. **Still true: BRE has never called a live Bob.** 329 tests pass on Windows (1 skipped: no bobide binary). |
| [0010](sessions/0010-demo-readiness-and-team-pack.md) | 2026-09-27 | Demo readiness and the team pack | @dee + Claude | S9 | closed | **Performing** the video script found 3 defects 330 green tests had missed; the worst: **Approve failed in every browser** (422 shown as `[object Object]`). Fixed on `demo-readiness`. Merge it before recording. Team dossier + zip built by `scripts/make_team_pack.py`. |

---

## Open threads across all sessions

Regenerate with:

```bash
grep -rn "Status:\*\* open" docs/memory/sessions/
```

The grep also returns entries closed by a *later* session (entries are append-only, so the
original line keeps saying `open`). Trust this table for closure, the grep for discovery.

| Session | Entry | Thread | Owner |
|---|---|---|---|
| 0001 | #7 | **Bob has never been called live.** Two adapters exist (Bob Shell CLI, 0007; agent-host WebSocket, 0005); both proven only against fakes or documentation. Close with `python scripts/verify_bob.py` (exit 0 + stamped artifact), then `docs/submission/BOB_USAGE_PLAN.md` Tasks B–D | **needs a human with Bob installed** |
| 0002 | #7 | `on_event` and `datetime.utcnow()` deprecations reproduce on 3.13; filtered, not fixed (old code only; new code uses aware UTC) | unassigned |
| 0004 | #2 | `eval:`-prefixed run ids can still close ledger records without a verification row. **Mitigated:** `OwnershipTable` joins to real `verification_runs`, so those closures never move reputation. The escape hatch itself remains | unassigned |
| 0005 | #2 | Agent-host WS: darwin has no host build; chat-channel encoding + turn-completion delivery unconfirmed against a real host | first linux/x64 or win32 run |
| 0007 | #11 | Campus network may have a TLS interception proxy — could break the Bob Shell install | unassigned |
| 0008 | #9 | Asymmetry test has almost no power at 1–4 agents; a 50+ contributor repo is the decisive follow-up, not run | unassigned |
| 0009 | #16 | **`Dockerfile` has never been built** (Docker Desktop was not running); the hosted demo depends on it | unassigned |
| 0009 | #14 | tau tuning is in-sample; token figures are nominal until a live Bob run; ownership evolution too slow at ASMOS's prior (α+β=10) to matter at this scale — a smaller prior is an explicit future experiment | unassigned |
| 0009 | #17 | Submission items only a person can do: Bob task-session screenshots from each member, demo video, hosting, the lablab form. *(Push/merge done: PR #2 merged 2026-09-26; 0010's fixes are on `demo-readiness`, awaiting merge.)* | **needs humans** |

**Closed:** 0001#8 (ownership asymmetry unmeasured) — closed by 0008#4 with a **negative result**.
0001#10 (nothing runtime-verified) — closed by 0002#4/#5. 0004#7 (token counts zero until Bob
lands) — closed by 0005#5 for the agent-host adapter; `BobShell` reports tokens natively.

**Closed by 0009:** 0003#7 (the three strict-xfail S1 gaps were fixed; the markers are gone).

**Reopened by reconcile (0009):** 0001#7. Session 0005 closed it on the strength of a CLI banner,
a lockfile parse and a fake host; no real turn was ever exchanged with Bob. That is a
*narrowing*, not a close, and the S4 exit criterion says "confirmed by a working call".
