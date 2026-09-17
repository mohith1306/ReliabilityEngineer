---
session: 0003
title: Bob interface documented
author: "@dee (with Claude Opus 5)"
stage: S4
started: 2026-09-17T12:10:00Z
ended: 2026-09-17T13:05:00Z
status: closed
---

## Context on entry

Read 0001 and 0002 close-outs and the stage tracker. Took thread 0001#7 — the largest
schedule risk in the project — on the reasoning that every stage from S4 onward was
planned against an interface nobody had confirmed existed.

Belief on entry: Bob is an IDE, so driving it programmatically might not be possible at
all, and the whole orchestration architecture might need inverting. That belief was
wrong in a good way.

## Entries

### 1. Nothing about Bob existed locally
- **Type:** finding
- **What:** No Bob binary, no `BOB_*` environment variables, no credentials, no notes or
  hackathon materials anywhere under the project tree or its parent.
- **Why:** Rules out the possibility that a teammate had already set this up and not said
  so. The unknown was genuinely unknown.
- **Evidence:** `which bob` → not found; `npm ls -g` shows no Bob package; `env | grep -i
  bob` empty; parent directory contains only this repo.
- **Status:** resolved

### 2. Bob Shell exists and is exactly the surface BRE needs
- **Type:** finding
- **What:** IBM Bob ships a CLI, Bob Shell, with a non-interactive mode:
  `bob run --format json --mode ask|plan|agent`, authenticated by `BOB_API_KEY`
  (scope: Inference). Supports `--workspace`, `--max-turns`, `--max-cost`,
  `--resume <task-id>`, `--disable-mcp`, `--disable-subagents`, `--disable-tool-groups`.
- **Why:** This was the project's single largest risk and it resolves favourably. The
  orchestration architecture does not need inverting.
- **Evidence:** https://bob.ibm.com/docs/shell/getting-started/start-bobshell-non-interactive
  and https://bob.ibm.com/docs/shell/getting-started/install-and-setup
- **Status:** resolved

### 3. The JSON result carries cost natively — ERRATA A8 dissolves
- **Type:** finding
- **What:** `--format json` emits `stats` with `total_tokens`, `input_tokens`,
  `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `cache_ratio`,
  `duration_ms`, `session_costs` and `tool_calls`.
- **Why:** ERRATA A8 said cost could not be reconstructed retroactively and had to be
  instrumented from the first call. It turns out Bob reports its own cost, so the ledger
  just records what Bob returns. Better than the plan.
- **Evidence:** documented schema, pinned in `tests/unit/test_bob_adapter.py::
  test_parses_documented_stats_block`.
- **Status:** resolved

### 4. `--max-turns` and `--max-cost` are native loop bounds — ERRATA A4 partly dissolves
- **Type:** finding
- **What:** Bob enforces a per-call agentic-turn cap and a spend cap itself.
- **Why:** A4 said the autonomous loop had no termination condition. Half of that is now
  Bob's job. BRE still owns the *cross-call* bound — how many reinvestigation cycles one
  incident may consume — which Bob cannot know about. ERRATA updated to say so rather
  than marking A4 closed.
- **Evidence:** `bob/adapter.py` passes both; `test_loop_bounds_are_native`.
- **Status:** resolved

### 5. Decision: `bob run` as the surface, not BRE-as-MCP-server
- **Type:** decision
- **What:** BRE calls Bob via the CLI. MCP deferred to S9 as an additive second surface.
- **Why:** Bob is an MCP *client*, so BRE could have been an MCP server Bob consults.
  That inverts the orchestration direction — Bob becomes the orchestrator and BRE a
  retrieval plugin, discarding the lifecycle, the risk gate and the verification loop.
  The direction of the call is the product thesis, not plumbing. **Rejected:** MCP as
  primary (inverts the product); UI automation of the IDE (fragile, unusable in CI,
  which is where incidents originate); waiting for a REST API (none is documented).
- **Evidence:** [ADR-0004](../decisions/ADR-0004-bob-invocation-surface.md).
- **Status:** resolved

### 6. The mode flag gives a structural read/write boundary
- **Type:** finding
- **What:** `ask` and `plan` cannot modify the workspace; only `agent` can. That maps
  onto BRE's stages directly: investigate and diagnose use `ask`, remediation planning
  uses `plan`, and only S6 uses `agent`.
- **Why:** Stages S2–S5 become read-only *structurally* rather than by convention. A
  developer cannot accidentally write from a diagnosis path, because the mode they are
  calling through physically cannot.
- **Evidence:** `BobMode.is_write_path`; `test_only_agent_mode_is_a_write_path`.
- **Status:** resolved

### 7. Bob does not report changed files — `changed_files` must come from git
- **Type:** finding
- **What:** The documented JSON result has no file-change list. `stats` is cost and
  timing only; `last_message` is prose.
- **Why:** `Remediation.changed_files` was implicitly assumed to come from Bob. It must
  be derived from git instead. That is the better source — git records what actually
  changed, not what the agent believes it changed — and S6 already required a git
  checkpoint for rollback, so it costs nothing extra.
- **Evidence:** documented schema lists no such field; recorded in ADR-0004 consequences.
- **Status:** resolved

### 8. Adapter built against the documented contract
- **Type:** change
- **What:** `bob/adapter.py` (332 lines): `BobMode`, `BobUsage`, `BobResult`,
  `parse_result`, `BobPreflight`, `BobAdapter` with `investigate` / `diagnose` /
  `plan_remediation` / `remediate`. Prompt goes on stdin, never argv. MCP and subagents
  disabled by default — both widen cost and blast radius in ways BRE cannot account for.
  `remediate()` raises `BobWriteRefused` unless `allow_writes=True` is passed explicitly,
  so the write path is grep-able rather than implicit.
- **Why:** ERRATA section B noted `diagnose` was missing from the section 16 adapter
  sketch while section 10 assigns root-cause reasoning to Bob. Fixed here.
- **Evidence:** `bob/adapter.py`; 15 unit tests in `tests/unit/test_bob_adapter.py`.
- **Status:** resolved

### 9. Suite green — 35 passed, 3 xfailed
- **Type:** verification
- **What:** The 15 new adapter tests cover argv construction, parsing of the documented
  stats block, graceful degradation on missing or garbage fields, the write guard, and
  that `preflight()` makes no billable call.
- **Why:** Everything except the live round trip is testable offline, and that is where
  most of the implementation risk actually sits.
- **Evidence:** `venv/Scripts/python.exe -m pytest` → `35 passed, 3 xfailed in 3.90s`.
- **Status:** resolved

### 10. Thread 0001#7 is NOT closed
- **Type:** blocker
- **What:** No live call has been made. Bob Shell is not installed on this machine and
  `BOB_API_KEY` is not set. `scripts/verify_bob.py` runs, detects both, refuses to
  proceed, and exits 2 without billing anything.
- **Why:** The thread asked for a *working call*, and the honest status is that the
  contract is read from documentation, not observed. Every claim in entries #2–#7 is
  documentation-derived. If Bob's real output differs from the documented schema,
  `test_parses_documented_stats_block` is where it will surface.
- **Evidence:** `venv/Scripts/python.exe scripts/verify_bob.py` → exit 2,
  "binary found: False", "BOB_API_KEY: NOT SET".
- **Status:** open
- **Unblocked by:** install Bob Shell, create an API key with Scope=Inference in the Bob
  web portal, set `BOB_API_KEY`, then run `scripts/verify_bob.py`. Exit 0 plus a stamped
  artifact under `docs/artifacts/` closes the thread and unblocks S4.

### 11. The campus network may have a TLS interception proxy
- **Type:** finding
- **What:** A documentation fetch failed once with "Self-signed certificate detected.
  Check your proxy or corporate SSL certificates," and the msys2 pip failure in session
  0002 had the same shape.
- **Why:** If Bob Shell's installer or its API calls hit the same interception, the
  install will fail in a way that looks like a Bob problem rather than a network one.
  Worth knowing before anyone burns an hour on it.
- **Evidence:** transient WebFetch SSL error; session 0002 entry #1.
- **Status:** open — speculative, single occurrence, may simply have been transient

## Close-out

- **Shipped:** Bob's interface documented rather than assumed — the project's largest
  schedule risk resolved favourably. `bob/adapter.py` with a guarded write path and 15
  tests. `scripts/verify_bob.py` as the one-command thread closer. ADR-0004 on the
  invocation surface, including why BRE is not an MCP server. ERRATA A4 and A8 updated —
  both turn out to have native support in Bob. S4 moved to BLOCKED with concrete criteria.
- **Open threads:** #7 still open — adapter is written but unverified against a live Bob
  (needs install + key) · 0001#8 ownership asymmetry unmeasured · 0002#7 deprecations
  filtered not fixed · 0003#11 possible TLS interception on the campus network
- **Next session should:** either install Bob Shell and run `scripts/verify_bob.py` to
  close #7, or — if credentials are not available yet — take thread 0001#8 instead by
  running ASMOS's `git_ownership.py` against a real repository. #8 needs no credentials
  and it tests the premise the whole routing story rests on.
- **Stage delta:** S4 NOT_STARTED → BLOCKED (adapter built, live call pending credentials)
