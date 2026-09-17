---
description: Open a new numbered session memory file and reconstruct entry context
argument-hint: <2-5 word slug for what this session is about>
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

Open a new working session on this repo.

## Steps

1. **Claim the next number.** Find the highest existing session file:
   `ls docs/memory/sessions/ | sort | tail -1`
   Also check for numbers claimed on the remote but not local:
   `git fetch origin --quiet && git log origin/main --oneline -- docs/memory/sessions/ | head -5`
   Take `highest + 1`, zero-padded to 4 digits.

2. **Reconstruct entry context before writing anything.** Read, in this order:
   - `docs/stages/STAGES.md` — the current stage and its exit criteria
   - `docs/memory/INDEX.md` — bottom 5 rows
   - the two most recent session files in full
   - any ADR referenced by an open thread
   Then run `grep -rn "Status:\*\* open" docs/memory/sessions/` and note what is unresolved.

3. **Create the file** at `docs/memory/sessions/NNNN-<slug>.md` from
   `docs/memory/TEMPLATE.md`. Slug = `$ARGUMENTS`, kebab-cased, describing the intended
   *outcome*. Fill the front matter: session number, title, author (git `user.name`),
   stage, `started` as ISO-8601 UTC, `status: open`.

4. **Write the "Context on entry" section yourself** — not a stub. State what you believe
   is true right now, which sessions you read, and what you expect to be wrong about. If
   you could not do step 2 properly, say so there explicitly.

5. **Report back to the user** in under 10 lines: session number and path, current stage,
   open threads you inherited, and the one thing you think this session should achieve.

Do not start implementation work in this command. Opening the session is the whole job.
