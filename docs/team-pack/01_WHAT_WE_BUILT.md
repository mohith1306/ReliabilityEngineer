# What we built — for someone who hasn't read the code

## The problem

An AI agent can produce a plausible fix quickly. That creates three questions the agent cannot answer about itself:

1. **Was it right?** A green build can be made green by deleting or skipping the failing test.
2. **Was it safe?** Which branch did it touch, who approved it, can it be undone exactly?
3. **Did we learn?** The same outage recurs; nobody remembers who diagnosed it correctly last time.

## The loop

```
Detect → Investigate → Diagnose → Assess risk → Approve → Remediate → Verify → Learn
                                                                          │
                                       fails? roll back, refute, retry — capped, never unbounded
```

| Step | What happens | Who/what does it |
|---|---|---|
| Investigate | Gather repository, git, test and CI evidence | BRE connectors (read-only) |
| Diagnose | Explain the root cause | **IBM Bob**, `ask` mode — cannot modify files |
| Assess risk | Score the change; every factor's points are stored | Deterministic classifier (no randomness) |
| Approve | A human approves; the record stores *who*, from an API key | Human via the dashboard/API |
| Remediate | Apply the fix on a fresh `bre/…` branch after a pinned git checkpoint | **IBM Bob**, `agent` mode — only here, only after approval |
| Verify | Run the failing test → its whole file → the entire suite | The target's real `pytest` |
| Learn | Confirmed diagnoses become memory; refuted ones cost the source standing | The outcome ledger + ASMOS ownership |

## Why the write path is trustworthy (the safety argument)

| Control | How it's enforced |
|---|---|
| Analysis is free; changing code is privileged | Read-only unless the repo is on an allowlist (deny by default) |
| A human is on the record | Identity comes from an **API key**, never from text in the request; re-checked inside the write engine |
| Never the default branch | Git checkpoint pinned first, then a fresh `bre/<incident>/attempt-<n>` branch; a dirty tree is refused |
| Changed files are facts | Recorded from `git diff`, not from what the agent says it changed |
| The agent can't cheat the suite | A diff guard rejects deleted / skipped / vacuous tests and CI-config edits |
| Failure leaves nothing behind | Exact rollback; your own untracked files are never touched; the rejected patch is kept as evidence |
| It stops | Attempt cap (default 3) → `ABANDONED`; untested attempts are *abandoned*, not *refuted* |
| One place writes | Exactly one `allow_writes=True` in the whole codebase (an automated test asserts it) |

## The ledger — "every prediction is written down before it's known"

Each diagnosis, risk level, routing decision and fix plan is recorded as **pending** the moment it is made. **Only a real verification run** may close it:
**confirmed** or **refuted**. If it never reached verification it is **abandoned** and moves no reputation. The verifier is a *deterministic test-suite exit code*,
not a model grading itself.

## The learning — ASMOS in plain words

ASMOS is the research mechanism this borrows. It keeps, per topic, a score for *who has been verifiably right*:

- `Trust = (7 + verified_correct) / (10 + verified_total)` — starts at 0.70 and moves only on verified outcomes
- `Ownership = 0.6 × Trust + 0.4 × Share`
- **Route to memory only if `Similarity × Ownership ≥ τ`**, otherwise run a full investigation with Bob

So BRE answers a *recurring* failure from **verified memory at zero Bob cost** when a past diagnosis has earned it, and falls back to Bob when nothing has. A cold start always falls back.
The ASMOS math is pinned to the real research code by 95 parity tests.

**The look-alike (the demo moment that matters):** an incident with the same symptom but a different cause. Memory answers, the patch is applied, **the tests refute it**, it's rolled back,
the memory loses standing, and a full investigation finds the real cause. *The agent was wrong; the system found out because the tests said so.*

## What we measured — and its limits

(Full report: [RESULTS.md](../RESULTS.md).)

| Scenario | Result |
|---|---|
| Failures that recur (10 incidents) | 6 served from verified memory, 0 refuted, ~24.8% lower **nominal** cost |
| With look-alike twins (14 incidents) | 13 routed to memory; the tests refuted 4 (the look-alikes), each rolled back and retried; resolution identical; ~10.1% lower nominal cost |
| Ownership-evolution ablation | **Flat** at this scale — reported as such |

**Limits, stated everywhere on purpose:** token costs are *nominal* (Bob is replayed, so they are placeholder prices × real counts); the corpus is small and synthetic; the threshold τ was tuned
on the same data it's evaluated on; nothing here says anything about IBM Bob's diagnostic quality.
We also made a mistake worth knowing about: our first threshold tuner said "never route", and the measurement showed the opposite; we replaced it with a simulator validated against 9 of 9 measured runs (ADR-0006).

## Glossary

| Term | Meaning |
|---|---|
| **BRE** | Bob Reliability Engineer — this project |
| **Bob Shell** | IBM Bob's command-line mode: `bob run --format json`, with `--mode` set to ask, plan or agent |
| **ASMOS** | The research project whose ownership/routing math BRE reuses; lives in a separate repo |
| **Outcome ledger** | Table where every prediction is recorded and later closed by verification |
| **Ownership** | How verifiably right a source (e.g. "memory") has been about a topic |
| **τ (tau)** | Threshold: route to memory only if the routing score reaches it |
| **Look-alike** | Same symptom and failing test as a past incident, different cause |
| **Simulated / replay Bob** | The labelled stand-in that replaces Bob when no credentials exist; never chosen automatically |
| **Cassette** | One scripted stand-in response for one failure scenario (`bob/cassettes/`) |
| **Session ledger** | The numbered files in `docs/memory/sessions/` — the team's memory across sessions |
| **Cockpit** | `python scripts/cockpit.py` — one screen of live project status and integrity checks |
| **Nominal** | A placeholder figure that keeps accounting exercised; not a measurement |
