---
description: Close the open session, update the index and the stage tracker
allowed-tools: Bash, Read, Edit, Glob, Grep
---

Close the open session cleanly so the next person can pick it up cold.

## Steps

1. **Find the open session file.** If none, say so and stop.

2. **Sweep for unlogged work.** Run `git status --porcelain` and `git diff --stat`. Every
   changed file should be traceable to an entry. If something changed that no entry
   mentions, add the missing entries now via the `/session-log` rules before closing.
   This is the most valuable step in the command — do not skip it.

3. **Write the close-out block:**

   ```markdown
   ## Close-out
   - **Shipped:** what is now true that was not true before
   - **Open threads:** each still-`open` entry by number, and who should pick it up
   - **Next session should:** the single most useful next action, specific enough to act on
   - **Stage delta:** e.g. S4 NOT_STARTED → IN_PROGRESS
   ```

   "Next session should" is not a wish list. One action, concrete.

4. **Update the front matter:** `ended` to ISO-8601 UTC now, `status: closed`
   (or `abandoned` if the session produced nothing worth carrying forward — that is an
   honest and acceptable outcome, and abandoned sessions still keep their number).

5. **Append the row to `docs/memory/INDEX.md`.** The final column is the one thing a
   stranger needs to know from this session — write it for someone who will never open
   the file.

6. **Update the open-threads table at the bottom of INDEX.md** from
   `grep -rn "Status:\*\* open" docs/memory/sessions/`. Remove threads that this session
   resolved; add ones it opened.

7. **Update `docs/stages/STAGES.md`** if the stage moved. A stage only reaches `DONE` when
   its exit criteria are met *and* the entry that proves it is cited in the Evidence
   column. If the criteria are not met, leave it `IN_PROGRESS` and say why in the session
   file. Do not mark a stage done to feel finished.

8. **Report back:** session number, what shipped, stage delta, and the next action.

Do not commit anything unless the user asks.
