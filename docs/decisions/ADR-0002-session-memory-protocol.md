# ADR-0002 — Session Memory Protocol

- **Status:** Accepted
- **Date:** 2026-09-17
- **Session:** [0001](../memory/sessions/0001-asmos-alignment-and-workflow.md)

## Context

This repository is built by a distributed team working alongside agents whose context dies
at the end of every session. Three kinds of knowledge were being lost:

- **why** a decision was made, when the diff only shows *what* changed
- **what was tried and rejected** — the expensive knowledge, which leaves no commit at all
- **where the build actually is**, as opposed to what the architecture document aspires to

The ASMOS repo hit the same problem and answered it with a single `SESSION_MEMORY.md`. That
file is good — dated, specific, cites tests and invariants — but it is one file, which does
not survive several people writing at once.

## Decision

An append-only ledger of numbered session files under `docs/memory/sessions/`, one per
working session, indexed in `INDEX.md`, specified in
[PROTOCOL.md](../memory/PROTOCOL.md), and enforced by the working agreement in
[CLAUDE.md](../../CLAUDE.md).

Four properties, each load-bearing:

1. **One file per session** — isolation, so concurrent teammates never edit the same lines.
2. **Sequential numbering, never reused** — the number is the ordering, and stable entry
   numbers make `0007#3` a durable cross-reference.
3. **Append-only; corrections supersede rather than overwrite** — the same rule the product
   applies to its own checkpoints (`supersedes` / `superseded_by`). A ledger you can quietly
   rewrite is not a ledger.
4. **Every entry carries evidence**, with `none (hypothesis)` as an explicit, honest value.

Claude Code slash commands (`/session-start`, `/session-log`, `/session-end`, `/catch-up`,
`/stage`) wrap the protocol. **The protocol is the contract; the commands are convenience.**
An agent without slash commands follows PROTOCOL.md by hand.

## Consequences

**Positive.** A teammate or a fresh agent can reconstruct project state in about ten minutes
from the ledger alone, with no live context. Rejected alternatives stay rejected. The
evidence rule keeps unverified beliefs visibly unverified — which is the same discipline the
product enforces on its own memory, so the repo dogfoods its thesis.

**Negative.** It is overhead, and overhead decays. If the ledger is skipped for a week it
becomes actively misleading, which is worse than absent — a stale ledger is read as current.
`/session-end` mitigates this by sweeping `git status` for unlogged changes before closing,
but the discipline still has to be kept.

**Operational.** Session numbers can collide when two people start simultaneously; PROTOCOL
resolves it by renaming the loser, since entry numbers inside a file never change.

## Alternatives rejected

- **A single shared `SESSION_MEMORY.md`** (the ASMOS approach). Rejected for merge conflicts
  under concurrent authorship. Correct for a solo or serial project; wrong for a team.
- **Git history as the memory.** Rejected: it records what changed, never what was considered
  and rejected, and dead ends are precisely the knowledge worth keeping.
- **Issue tracker or external doc.** Rejected: an agent with only a checkout cannot read it.
  The memory must ship with the code.
- **Auto-generated summaries at session end.** Rejected for now: a summary written without
  the evidence rule produces confident, unfalsifiable prose. The value is in the discipline
  of citing evidence, which automation would remove.
