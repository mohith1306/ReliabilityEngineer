# ADR-0005 — Bob surfaces, and a labelled stand-in for running without Bob

- **Status:** Accepted — **unverified against a live Bob** (see Consequences)
- **Date:** 2026-09-27
- **Session:** [0009](../memory/sessions/0009-reconcile-and-build-s6-s9.md)
- **Supersedes:** the "adapter" half of [ADR-0004](ADR-0004-bob-invocation-surface.md) where they differ; ADR-0004's
  conclusion (BRE calls Bob, not the reverse) stands.

## Context

Two lines of work reached the same stage from opposite ends and produced two incompatible Bob adapters:

- **Bob Shell** — `bob run --format json --mode ask|plan|agent`, from IBM's own documentation. Reports its own
  tokens and cost; the only surface with a write mode. Never run against a live Bob (no install, no key).
- **Agent-host WebSocket** — JSON-RPC over the IDE's local host, recovered by inspecting the shipped binaries.
  Undocumented; IBM publishes no darwin host build, so it never completed a real round trip and is proven only against
  a hand-built fake. Its turn-completion detection and chat-channel encoding are guesses.

And a third need: CI, a contributor without a key, and a public demo all need the *rest* of BRE to run with no Bob at all.

## Decision

1. **Bob Shell is the primary surface.** It is documented, it reports cost natively, and it is the only one that can
   write. `select_transport()` prefers it whenever `bob` is on PATH and `BOB_API_KEY` is set.
2. **The agent host is kept, as experimental and read-only.** Deleting a teammate's working code to win an argument is
   the wrong trade; it may become useful on win32/linux where IBM does publish a host. It is never used for remediation.
3. **Both sit behind one `Transport` contract** (`bob/transport.py`) under one adapter and one exception root, so the
   loop does not know or care which carried a turn.
4. **A replay stand-in exists, and it is fenced.** It runs only when `BRE_BOB_TRANSPORT=replay` is set explicitly — never
   automatically, never as a silent fallback. Every turn it produces is flagged `simulated`, that flag is written into the
   outcome ledger, and the dashboard shows **SIMULATED BOB** on every screen. It matches on an *anchored failure
   signature in the repository*, so a repo that does not exhibit a recorded failure — including one already fixed — gets
   an honest "no recorded response". Its executor *follows the diagnosis it is handed*, so a wrong diagnosis produces a
   wrong fix and the test suite, not the stand-in, decides.
5. **The write path has exactly one authorisation site.** `BobShellExecutor` contains the only `allow_writes=True` in the
   codebase, asserted by an AST test. It runs only inside `RemediationEngine.run`, behind the approval gate, the
   allowlist, a git checkpoint and branch-only writes.
6. **Real Bob output can be recorded** (`BRE_BOB_RECORD_DIR`), so a live session leaves proof of use and a genuine
   recording to replay when the allowance runs out. The recorder refuses to write inside the repository under repair.

**Rejected:** picking one adapter and deleting the other (discards the only working code for the loser's environment);
silently falling back to replay when Bob is missing (a demo that quietly lies is worse than one that stops);
making the replay stand-in smarter so it "diagnoses" arbitrary repos (that is writing a coding agent — CLAUDE.md
non-negotiable 1); MCP as the primary surface (ADR-0004: it inverts the product).

## Consequences

- **The single largest open risk is unchanged: BRE has never talked to a live Bob.** Every "Bob" claim is
  documentation-derived or stand-in-derived. `python scripts/verify_bob.py` (exit 0 + stamped artifact) is the one command
  that closes it, and it needs a person with Bob Shell installed and a key. See `docs/submission/BOB_USAGE_PLAN.md`.
- Token figures produced through replay are **nominal** (`usage_is_simulated`). They keep the cost plumbing exercised;
  they are not measurements and must never be reported as such. The evaluation harness says this in every artifact.
- Cassettes are hand-authored. They are evidence about BRE's plumbing and safety properties, and none at all about Bob's
  diagnostic quality.
- `bob run` in `agent` mode has never been observed. Whether real Bob leaves uncommitted changes, commits on its own, or
  touches files the guard will reject is unknown until Task B in the usage plan is run.
