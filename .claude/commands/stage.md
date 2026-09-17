---
description: Show or advance the build stage tracker
argument-hint: [advance <id> | block <id> <reason> | show]
allowed-tools: Bash, Read, Edit, Grep
---

Read or update `docs/stages/STAGES.md`.

## `show` (default, also when $ARGUMENTS is empty)

Print a compact view: every stage with status, and for the current one its exit criteria
and which are met. Then state the single thing blocking progress.

## `advance <id>`

1. Read the stage's **exit criteria**. Check each one *by running the check*, not by
   reading the code and forming an impression. A criterion that cannot be checked by a
   command is a badly written criterion — say so and propose a better one.
2. If any criterion fails, refuse to advance. Report which failed and what the actual
   result was. This refusal is the command's main purpose.
3. If all pass: set status to `DONE`, fill the `Evidence` column with the command output
   or session entry that proves it, and set the next stage to `IN_PROGRESS`.
4. Log a `verification` entry in the open session file recording the checks and results.

## `block <id> <reason>`

Set the stage to `BLOCKED`, record the reason and what would unblock it, and open a
matching `blocker` entry in the current session file.

## Rules

- A stage is never `DONE` without evidence in the Evidence column.
- Dependencies are enforced: do not set a stage `IN_PROGRESS` while a stage it depends on
  is `NOT_STARTED` or `BLOCKED`. If the user wants to anyway, log it as a `decision` entry
  with the reasoning.
- The tracker reflects reality. If the real state and the file disagree, fix the file and
  log a `finding` entry about the drift.
