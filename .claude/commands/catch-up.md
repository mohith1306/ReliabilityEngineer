---
description: Rebuild full project context from the session ledger before doing any work
argument-hint: [number of recent sessions to read, default 5]
allowed-tools: Bash, Read, Glob, Grep
---

Reconstruct context from the ledger. Run this when joining the project, returning after
time away, or taking over a teammate's thread. Read-only — change nothing.

## Steps

1. **Where is the build?** Read `docs/stages/STAGES.md` in full. Note the current stage,
   its exit criteria, and which stages are blocked.

2. **What has happened?** Read `docs/memory/INDEX.md`. Take the last N rows
   (`$ARGUMENTS`, default 5) and read those session files in full — particularly each
   "Close-out" and "Context on entry".

3. **What is unresolved?**
   ```bash
   grep -rn "Status:\*\* open" docs/memory/sessions/
   ```
   Every hit is a live thread. Cross-check against the open-threads table in `INDEX.md`;
   if they disagree, the grep is authoritative and the table is stale — note it.

4. **What is already decided?** List `docs/decisions/`. Read every ADR referenced by an
   open thread or by the current stage. Decisions here are closed — do not relitigate
   them without an explicit new ADR.

5. **What does the architecture actually say?** Read
   `docs/architecture/ERRATA.md` before trusting `docs/ARCHITECTURE.md`. The long-form doc
   is aspirational and contains known inaccuracies; the errata lists them.

6. **Only now, read code** — and only the files the open threads point at.

## Report

Give the user a briefing of at most 20 lines:

- **Stage:** current stage, status, what closes it
- **Last 3 sessions:** one line each, what changed
- **Open threads:** numbered, with owner if known
- **Decided, do not revisit:** ADRs in force
- **Sharpest risk right now:** your own read, stated as opinion
- **Recommended next action**

If the ledger is thin or contradictory, say that plainly rather than inventing a coherent
story from it.
