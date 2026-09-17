# Session Memory Protocol

Agent-agnostic. Claude Code wraps this in slash commands; IBM Bob, another agent, or a
human follows it by hand. The protocol is the contract.

---

## Why one file per session

Alternatives considered and rejected:

| Option | Why not |
|---|---|
| One shared `SESSION_MEMORY.md` | Every teammate edits the same lines. Guaranteed merge conflicts; the ledger becomes the most painful file in the repo and people stop updating it. |
| Git history as the memory | Records *what* changed, never *why it was considered and rejected*. Dead ends are the expensive knowledge and they leave no commit. |
| Issue tracker | Lives outside the repo, so an agent with only a checkout cannot read it. |

One append-only numbered file per session gives isolation (no two people write the same
file), ordering (the number is the sequence), and locality (it ships with the checkout).

---

## File layout

```
docs/memory/
  PROTOCOL.md          this file
  INDEX.md             one line per session, newest last — the table of contents
  TEMPLATE.md          copy this to start a session
  sessions/
    0001-<slug>.md
    0002-<slug>.md
    ...
```

- Numbers are **4-digit, zero-padded, strictly increasing, never reused.**
- The slug is 2–5 kebab-case words describing the session's *outcome*, not its activity.
  `0007-bob-adapter-spike` ✅  `0007-more-work` ❌
- Files are **append-only during the session.** Correcting an earlier entry means adding a
  new entry that supersedes it, not editing history. (Same rule the product applies to
  checkpoints: `supersedes` / `superseded_by`, never silent edits.)

## Claiming a number without colliding

Two teammates starting at the same time will both want `0009`. Resolve it the cheap way:

```bash
ls docs/memory/sessions/ | tail -1          # highest existing number
git fetch origin && git log origin/main --oneline -- docs/memory/sessions/ | head -5
```

Take `highest + 1`. If you lose the race on push, **rename your file to the next free
number** and fix its `INDEX.md` line. Entry numbers *inside* the file never change.

---

## Session file structure

Front matter, then numbered entries, then a close-out block.

```markdown
---
session: 0007
title: Bob adapter spike
author: <name or agent id>
stage: S4
started: 2026-09-17T14:02:00Z
ended: 2026-09-17T17:40:00Z
status: closed          # open | closed | abandoned
---

## Context on entry
<what you believed to be true when you started, and which sessions you read to get there>

## Entries

### 1. <short title>
- **Type:** decision | finding | change | blocker | question | verification
- **What:** one or two sentences
- **Why:** the reasoning that a reader cannot reconstruct from the diff
- **Evidence:** `path/to/file.py:42`, command output, artifact path — or `none (hypothesis)`
- **Status:** open | resolved | superseded-by-#N

### 2. ...

## Close-out
- **Shipped:** what is now true that was not true before
- **Open threads:** numbered entries still `open`, and who should pick them up
- **Next session should:** the single most useful next action
- **Stage delta:** S4 NOT_STARTED → IN_PROGRESS
```

### Entry types

| Type | Use for |
|---|---|
| `decision` | An alternative was closed off. Must record what was rejected and why. |
| `finding` | Something true about the system that the repo did not already state. |
| `change` | Behaviour, schema, or interface changed. Must cite the files. |
| `blocker` | Work stopped. Must state exactly what would unblock it. |
| `question` | An unknown that matters. Must state who or what can answer it. |
| `verification` | A claim was tested. Must cite the command and its result, pass or fail. |

A `verification` entry that records a failure is worth more than one that records a pass.
Log failures.

---

## Evidence rule

Every entry has an `Evidence` line. Permitted values:

- a repo path with optional line number — `reliability/risk/classifier.py:88`
- a command and its outcome — `pytest tests/unit -q → 41 passed, 2 failed`
- an artifact path — `docs/artifacts/e1_routing_20260917.json`
- an external reference — a commit SHA, PR URL, doc link
- `none (hypothesis)` — explicitly marks the entry as unverified

The last value is not a loophole, it is the point: an unverified belief recorded *as*
unverified is useful; an unverified belief recorded as fact poisons every session after it.

---

## INDEX.md line format

One line per session, appended on close:

```
| 0007 | 2026-09-17 | Bob adapter spike | @dee | S4 | closed | Bob has no public HTTP API in the hackathon env; adapter must shell out |
```

The last column is the **one thing a stranger needs to know** from that session. Write it
for someone who will never open the file.

---

## Reconstructing context (the `catch-up` procedure)

When you join, return after time away, or take over someone's thread:

1. Read `docs/stages/STAGES.md` — where the build is.
2. Read `INDEX.md` bottom-up until you have ~5 sessions of context.
3. Open the last 2 session files in full.
4. Grep the ledger for open threads: `grep -rn "Status:\*\* open" docs/memory/sessions/`
5. Read any ADR referenced by those entries.
6. Only then read code.

Steps 1–5 take about ten minutes and save an afternoon of re-deriving decisions that were
already made and already rejected.
