---
session: 0011
title: Video walkthrough page and the four-speaker split
author: "@dee (with Claude, Claude Code)"
stage: S9 (submission)
started: 2026-09-27T14:00:00+05:30
ended: 2026-09-27T14:30:00+05:30
status: closed
---

## Context on entry

PR #14 merged at the user's request (`2df173f`, 08:31 UTC). Asked for a neat, stable HTML demo file that matches the video script exactly, with dark and
light mode; and a `recommendation.md` saying what each of the four team members should speak about, one image each. Read session 0010 and
`docs/submission/VIDEO_SCRIPT.md` on entry.

## Entries

### 1. The script's slot timings could not be spoken
- **Type:** finding
- **What:** counting words per beat: 438 in total (fits 3:00 at ~150–160 wpm), but the results beat had 98 words in a 20 s slot (~290 wpm) and "say what is real" had
  36 words in 10 s, while the risk beat had 30 s for ~15 s of speech. Re-timed every slot to its word count at ~160 wpm, with clicking done while talking;
  **no words changed.** New boundaries: 0:00 · 0:12 · 0:26 · 0:43 · 0:53 · 1:14 · 1:26 · 1:44 · 2:17 · 2:54 · 3:00.
- **Why:** whoever had the results beat would have had to rush it or run the video over 3:00, on the beat that must say "nominal".
- **Evidence:** word counts computed from the spoken track in the walkthrough page; `docs/submission/VIDEO_SCRIPT.md` headings; `03_PRESENTING_AND_JUDGE_QA.md` outline updated to match.
- **Status:** resolved

### 2. "Replace 'the agent' with 'Bob' throughout" would make two live lines untrue
- **Type:** finding
- **What:** the script's LIVE rule was a blanket substitution. It would have said "we measured it against Bob alone" (the comparison used the stand-in)
  and "Bob was wrong" (the wrong answer in the look-alike was a *reused* diagnosis). Replaced the rule with an exact table of six live lines.
- **Why:** a live recording is where a judge is most likely to take a sentence literally.
- **Evidence:** `docs/submission/VIDEO_SCRIPT.md` "If the recording is LIVE"; the page's Live switch changes exactly beats 2, 3, 5, 7, 8, 9 (checked in the browser).
- **Status:** resolved

### 3. `docs/submission/demo_walkthrough.html`
- **Type:** change
- **What:** one self-contained page (no network): a timeline, then per beat a static mock of the dashboard with its exact on-screen text beside the words to say,
  with Why / Source / Checked underneath. Also a Simulated/Live switch, light/dark theme (system default + toggle), a rehearsal timer, keyboard navigation,
  speaker names, the pre-flight checklist, the spoken track, troubleshooting, and a print view. No animations; the mock is laid out at one width and scaled as a whole.
- **Why:** the user asked for something simple and steady to explain from; the page is for rehearsal and for teammates, while the video records the real dashboard.
- **Evidence:** checked in the browser at 800, 1100, 1366 and 1920 px: no overflow on any of 17 screens × 2 modes, no horizontal scroll, and the mock's top edge at one
  position on every screen; no console errors. Automated comparison: all 10 spoken lines identical to the script's spoken track and per-beat Say lines.
  Risk-tab text captured verbatim from the running dashboard. Bug found and fixed while checking: a function named `top` collided with `window.top` and stopped the script.
- **Status:** resolved

### 4. `docs/submission/recommendation.md`: four speakers
- **Type:** change
- **What:** split 43 / 43 / 51 / 43 s (103 / 103 / 119 / 113 words): problem + honesty + the gate · the write path · learning + the look-alike · results + close.
  For each: the one idea owned, the exact lines, what to stress, what is on screen, what never to say, and the judge question to own. Image guidance: a corner card for ~2 s,
  never a full-screen cut. A fallback section if the "four images" are the members' Bob task-session screenshots.
- **Why:** the user said the explanation is what matters most.
- **Evidence:** the quoted lines were compared programmatically with the script's spoken track: identical, in order.
- **Status:** resolved

### 5. The real, working dashboard inside the walkthrough; served at `/walkthrough`
- **Type:** change
- **What:** asked to include the real working demo. The page's *On screen* panel now switches between the script mock and **Real dashboard**, an embedded, clickable
  dashboard loaded once and kept alive across beats. BRE serves the page at `GET /walkthrough` (same origin as `/`), so it can read `/api/system` and **warn when its
  LIVE/SIMULATED wording disagrees with the server** (or the server has NO BOB). Opened as a file, it embeds `http://127.0.0.1:8000/` and says it can't check the mode.
  `scripts/run_demo.*` print the walkthrough URL.
- **Why:** the recording is of the real dashboard; rehearsing next to the real thing removes the translation step, and the mode check enforces rule 1 automatically.
- **Evidence:** `apps/api/main.py` (`walkthrough`); `tests/integration/test_api_loop.py::test_the_video_walkthrough_is_served_beside_the_dashboard`. In the browser, via
  `scripts/run_demo.ps1 -Port 8765`: status *Connected · SIMULATED BOB · τ 0.3 · demo mode*; Live wording → the warning appears; incident 1 run end to end inside the
  frame (Run → Approve → Run → RESOLVED); the frame did not reload across all 10 beats; no clipping at 567 and 1366 px (a stacked-layout clipping bug found and fixed).
- **Status:** resolved

## Close-out

- **Shipped:** the walkthrough page, the four-speaker recommendation, a speakable script timing, exact live lines.
- **Open threads:** unchanged: 0001#7 live Bob, 0009#16 Dockerfile, 0009#17 human-only submission items.
- **Next session should:** record the video (#10) following the walkthrough; fill the speakers' names and roles.
- **Stage delta:** none.
