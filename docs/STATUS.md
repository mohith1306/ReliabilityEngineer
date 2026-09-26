# Project status

> **Generated** by `python scripts/cockpit.py --write` at Sun 2026-09-27 02:51 India Standard Time, commit `705b335`. Do not edit by hand -- it is regenerated from git, the ledger, the stage tracker and the last test run. For the *why*, read `docs/memory/INDEX.md`.

```text
BRE COCKPIT                                           Sun 2026-09-27 02:51 India Standard Time

== CLOCK =====================================================================
deadline  Sun 2026-09-27 20:30 India Standard Time  (11:00 AM EDT)
remaining 17h 38m

== GIT =======================================================================
branch    integration/reconcile-main @ 705b335  The loop over HTTP, the dashboard, demo mode, and de
vs main   11 ahead / 0 behind origin/main (22cd27a)
upstream  (none -- this branch exists only locally)
worktree  26 uncommitted path(s)

== STAGES ====================================================================
S0  DONE         ............  0/0  Alignment + working agreement
S1  DONE         ............  0/0  Foundation — models, state machine, DB
S2  DONE         ############  6/6  Evidence collection — connectors + inv
S3  DONE         ############  5/5  Outcome ledger + evaluation harness
S4  BLOCKED      ##########..  5/6  Bob adapter — **read paths only**
S5  DONE         ############  5/5  Risk engine + approval gate
S6  DONE         ############  8/8  Remediation — the write path
S7  DONE         ############  9/9  Verification + rollback + bounded feed
S8  DONE         ############  9/9  ASMOS ownership routing + learning
S9  DONE         ############  4/4  Metrics, baseline comparison, demo
------------------------------------------------------------------------------
current   none — S0–S3 and S5–S9 are DONE; **S4 is BLOCKED on a human** (liv
blocked   S4 live verification (and S6's live agent-mode call) — needs Bob S
risk      **Bob has never been called live.** Both adapters (Bob Shell CLI, 

== TESTS =====================================================================
GREEN  329 passed, 0 failed, 0 errors, 1 skipped, 0 xfailed @ 705b335   (stale: code changed since)

== SUBMISSION (lablab.ai) ====================================================
HUMAN 5  TODO 7
   1 TODO     agent       Project title
   2 TODO     agent       Short description
   3 TODO     agent       Long description
   4 TODO     agent+human IBM Bob usage statement
   5 TODO     agent       Technology & category tags
   6 HUMAN    human       Public code repository
   7 HUMAN    human       IBM Bob task-session summary screenshots, **
   8 HUMAN    human       Demo application platform
   9 HUMAN    human       Application URL
  10 TODO     agent       Cover image
  11 HUMAN    human       Video demonstration
  12 TODO     agent       Slide presentation

== OPEN THREADS ==============================================================
0001#7  [needs a human with] Bob has never been called live. Two adapters e
0002#7  [unassigned] on_event and datetime.utcnow() deprecations re
0004#2  [unassigned] eval:-prefixed run ids can still close ledger 
0005#2  [first linux/x64 or] Agent-host WS: darwin has no host build; chat-
0007#11 [unassigned] Campus network may have a TLS interception pro
0008#9  [unassigned] Asymmetry test has almost no power at 1–4 agen
0009#16 [unassigned] Dockerfile has never been built (Docker Deskto
0009#14 [unassigned] tau tuning is in-sample; token figures are nom
0009#17 [needs humans] Submission items only a person can do: Bob tas
------------------------------------------------------------------------------
last sessions: 0007 Bob interface document | 0008 Asymmetry measured, pr | 0009 Reconcile two lines, b

== INTEGRITY =================================================================
14/15 checks pass
  FAIL  doc links resolve: 1 broken, e.g. README.md -> docs/STATUS.md

== NEXT ======================================================================
1. FIX INTEGRITY FIRST: doc links resolve
2. Needs a person: #6 Public code repository; #7 IBM Bob task-session summary
3. 11 commit(s) ahead of origin/main exist only locally -- the judged repo do
```
