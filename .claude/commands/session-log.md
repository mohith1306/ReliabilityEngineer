---
description: Append a numbered entry to the current open session memory file
argument-hint: <what happened — a sentence is enough, or leave blank to infer>
allowed-tools: Bash, Read, Edit, Glob, Grep
---

Append one entry to the open session file.

## Steps

1. **Find the open session.** The highest-numbered file in `docs/memory/sessions/` whose
   front matter says `status: open`. If none is open, tell the user to run
   `/session-start` first and stop — do not invent a file.

2. **Determine the next entry number.** Highest `### N.` in that file, plus one. Entry
   numbers are never reused and never renumbered, even if an earlier entry turned out to
   be wrong.

3. **Write the entry.** Subject is `$ARGUMENTS` if given; otherwise infer it from the work
   done since the last entry in this conversation.

   ```markdown
   ### N. <short title>
   - **Type:** decision | finding | change | blocker | question | verification
   - **What:** one or two sentences
   - **Why:** the reasoning a reader cannot reconstruct from the diff
   - **Evidence:** <file:line | command → result | artifact path | none (hypothesis)>
   - **Status:** open | resolved | superseded-by-#N
   ```

4. **Enforce the evidence rule.** Every entry needs an `Evidence` line. If the claim is
   not backed by a file reference, a command you actually ran, or an artifact, write
   `none (hypothesis)` and set `Status: open`. Never dress an assumption as a finding.

5. **Pick the type honestly.**
   - `decision` must name the alternative that was rejected and why.
   - `blocker` must state exactly what would unblock it.
   - `verification` must cite the command and its real result. **Log failures** — a
     recorded failure is worth more than a recorded pass.
   - `change` must cite the files touched.

6. **If this entry contradicts an earlier one**, do not edit the earlier entry. Add this
   one, and set the earlier entry's status to `superseded-by-#N`. That edit is the only
   permitted modification to an existing entry.

7. **Report back in two lines**: entry number and its one-line summary.
