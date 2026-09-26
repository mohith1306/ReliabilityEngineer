# Submission checklist — IBM Bob 2.0 Hackathon (lablab.ai)

**Deadline: Sun 2026-09-27, 11:00 AM EDT = 20:30 IST** (source:
<https://lablab.ai/ai-hackathons/ibm-bob-2-hackathon>, read 2026-09-27).

**Judging criteria:** Application of Technology (a *clear* application of IBM Bob 2.0) ·
Presentation · Business Value · Originality.

**Rules that bite:** the repo must be **public**; it must contain the code/files where Bob
assisted **plus Bob task-session summary screenshots from each team member**; submissions must be
original and MIT-compliant. Bob access is time-limited and usage-limited — spend it deliberately.

Status vocabulary — `DONE` verified · `DRAFTED` an agent produced it, a human must review ·
`TODO` nobody has started · `HUMAN` only a person can do it (credentials, a camera, an account) ·
`BLOCKED` waiting on something named in Notes. The cockpit (`scripts/cockpit.py`) parses the
Status column, so keep it to one of those words.

| # | Item | Owner | Status | Notes |
|---|---|---|---|---|
| 1 | Project title | agent | DRAFTED | `SUBMISSION.md` §1 |
| 2 | Short description | agent | DRAFTED | `SUBMISSION.md` §2 |
| 3 | Long description | agent | DRAFTED | `SUBMISSION.md` §3 — includes the measured results with their caveats |
| 4 | IBM Bob usage statement | agent+human | DRAFTED | `SUBMISSION.md` §4 has `[TEAM: …]` markers that only the real Bob sessions can fill. Do not submit them unfilled |
| 5 | Technology & category tags | agent | DRAFTED | `SUBMISSION.md` §5 |
| 6 | Public code repository | human | HUMAN | Repo is PUBLIC (verified via `gh`). Integration branch is local-only until someone pushes/merges it |
| 7 | IBM Bob task-session summary screenshots, **each team member** | human | HUMAN | Cannot be faked or generated. Plan in `BOB_USAGE_PLAN.md` |
| 8 | Demo application platform | human | HUMAN | Needs an account (Render / Railway / HF Spaces / Vercel). Agent prepares the container config |
| 9 | Application URL | human | HUMAN | Follows item 8 |
| 10 | Cover image | agent | DRAFTED | `docs/submission/cover.png` (1280×720; regenerate with `scripts/make_cover.py`) |
| 11 | Video demonstration | human | HUMAN | Needs a person on camera/screen. Agent writes the script and a one-command demo |
| 12 | Slide presentation | agent | DRAFTED | `docs/submission/BRE_pitch.html` — 12 slides, numbers read from the artifacts; yellow TEAM box on slide 4 must be updated; Ctrl+P → PDF |
