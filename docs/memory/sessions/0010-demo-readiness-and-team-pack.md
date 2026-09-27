---
session: 0010
title: Demo readiness and the team pack
author: "@dee (with Claude, Claude Code)"
stage: S9 (submission)
started: 2026-09-27T03:10:00+05:30
ended: 2026-09-27T06:30:00+05:30
status: closed
---

## Context on entry

Continuation of 0009 (read its close-out). Asked for three things: put the work on GitHub where a remote teammate can follow it; finish a
zip-able team folder; and write a full video script where **every line carries its reason and source**, checked against reality.
Mid-session the user added: act as an inspector for demo-time problems, review the GitHub issues, and prepare a dossier for the team.
Belief on entry: the dashboard flow worked, because `tests/integration/test_api_loop.py` exercises it over HTTP. **Wrong**, see #3.

## Entries

### 1. GitHub tracking set up; PR #2 has since been merged
- **Type:** change
- **What:** pushed `integration/reconcile-main`, opened PR #2, a milestone due 2026-09-27T15:00Z (= 20:30 IST), a pinned tracker (#3) and one issue per remaining human task (#4–#13).
  PR #2 was then merged by `csdeepak` at 2026-09-26T22:18Z (merge commit `cdcdd33`). This session's later work is on a new branch, `demo-readiness`, cut from that `main`.
- **Why:** the teammates are remote, and the judged repository is `main`.
- **Evidence:** `gh pr view 2 --json mergedAt,mergedBy`; `git rev-list --left-right --count origin/main...HEAD` = `1 0` before branching.
- **Status:** resolved

### 2. The video script was checked by performing it, not by reading it
- **Type:** verification
- **What:** ran the dashboard in demo mode (`BRE_DEMO=1 BRE_BOB_TRANSPORT=replay BRE_TAU=0.30`, port 8765) and clicked through every beat: incident 1 → approve → RESOLVED;
  incident 2 answered from memory (`similarity 1.00 x ownership 0.42 = 0.42 >= tau 0.30`, 0 tokens); the look-alike (memory at ownership 0.63 → refuted → rolled back →
  attempt 2 finds `min(size, 2)` in `dbpool.py` → RESOLVED); learned tab (memory 0.542, bob 0.703); evaluation tab. Each Run click took under 4 s.
  On-screen strings in `docs/submission/VIDEO_SCRIPT.md` are copied from the page.
- **Why:** a script that has never been performed is a hypothesis. It found three defects (#3–#5) that 330 green tests had not.
- **Evidence:** `docs/submission/VIDEO_SCRIPT.md` ("Checked" line on each beat); the ownership arithmetic 0.6·(7.5/11)+0.4·(1/3) = 0.542 matches the tab.
- **Status:** resolved

### 3. Approve was broken in every browser; the API tests could not see it
- **Type:** finding
- **What:** the dashboard's `api()` helper built `fetch(path, { headers: merged, ...opts })`. The approval call is the only one that passes `headers` (for `Authorization`), and the spread replaced the merged object, dropping `Content-Type`.
  FastAPI returned 422, which the UI printed as `[object Object]`. Fixed by destructuring `headers` out of `opts` first; error details are now rendered as text.
- **Why:** the HTTP tests use `TestClient` with a correct JSON body, so the server was right and the browser was wrong. Only performing the demo showed it. Pinned with a source-shape test, which fails against the old helper.
- **Evidence:** `apps/web/index.html` (`const { headers, ...rest } = opts`); `tests/integration/test_api_loop.py::test_the_dashboard_api_helper_keeps_content_type_when_an_authorization_header_is_passed`.
- **Status:** resolved

### 4. A cached dashboard kept running the bug after the fix
- **Type:** finding
- **What:** after the fix a plain reload still ran the old helper (`api.toString()` in the page showed the old code while `GET /` served the new). `/` is now served with `Cache-Control: no-cache`.
- **Why:** a teammate who opened the dashboard yesterday would see the bug on the recording day with the fix merged.
- **Evidence:** `apps/api/main.py` (`dashboard()`); asserted in `test_the_dashboard_is_served_at_the_root`.
- **Status:** resolved

### 5. The replay stand-in matched `pool_size: 2` inside `pool_size: 20`
- **Type:** finding
- **What:** on the look-alike (config already 20, cap in code), `str.count("pool_size: 2")` found one hit inside `pool_size: 20`. The "restore to 20" edit therefore wrote `200`, and the
  labelled `when_misapplied` path never ran. The Patch tab showed the summary "Restore database.pool_size to 20" over a `20 → 200` diff. The executor now matches whole tokens (`_token_starts`), so the
  wrong fix is labelled *"(applied to a repository it does not fit)"* and the diff is `20 → 40`.
- **Why:** the outcome was right for the wrong reason, and the contradiction would have been on camera. **Measured results are unaffected:** the cap is in code, so either wrong edit fails the same test;
  token figures come from the cassette's `usage_tokens`, not from the edit. The artifacts were not regenerated.
- **Evidence:** `reliability/remediation/executors.py` (`_token_starts`); `test_a_lookalike_is_refuted_over_http_and_the_incident_recovers` now asserts the label and the `20 → 40` diff.
- **Status:** resolved

### 6. `.env` could be copied into the Docker image
- **Type:** finding
- **What:** `.dockerignore` excluded `*.db` and `venv` but not `.env`, so `docker build` in a checkout holding a real `BOB_API_KEY` would bake it into the image. Added `.env`, `.env.*` (keeping `.env.example`), `recordings` and `dist`.
- **Why:** Task B tells people to put a key in their environment on the same day someone builds the image.
- **Evidence:** `.dockerignore`. The image is still unbuilt (0009#16), so this is a static fix only.
- **Status:** resolved

### 7. Demo-day inspection and GitHub issue review, written up as the team dossier
- **Type:** change
- **What:** 15 risks (R1–R15) with likelihood, impact and status, plus a one-by-one review of the 11 open issues (none assigned, none commented), in `docs/team-pack/05_TEAM_DOSSIER.md`.
  On GitHub: closed #4 (its PR was merged), and pointed tracker #3, #10 and #11 at `main` instead of the old branch.
- **Why:** the user asked for an inspector's view before a day where people, not code, are the critical path.
- **Evidence:** `docs/team-pack/05_TEAM_DOSSIER.md` §3–§4; `gh issue view 3|4|10|11`.
- **Status:** resolved

### 8. The team pack is built by a script and tested
- **Type:** change
- **What:** `scripts/make_team_pack.py` writes `dist/BRE-team-pack/` and `dist/BRE-team-pack.zip`: guides 00–05 and the video script at the top, a `reference/` mirror of the key documents at their repo paths,
  and `MANIFEST.txt` (commit, sha256 per file). Relative links are rewritten to the copy in the pack, or to GitHub `main` for anything the pack does not carry. It refuses to delete an output folder it did not mark.
- **Why:** the pack is shared as a zip away from the repository; a dead link there costs a teammate time on the one day there is none.
- **Evidence:** `tests/unit/test_team_pack.py` (5 tests, including "every relative link resolves inside the pack" and "manifest hashes match the zip").
- **Status:** resolved

### 9. Suite
- **Type:** verification
- **What:** 335 passed, 1 skipped (no Bob binary), 0 failed on Windows, CPython 3.13.7, branch `demo-readiness`.
- **Evidence:** `venv\Scripts\python.exe -m pytest`.
- **Status:** resolved

## Close-out

- **Shipped:** the Approve button works in a browser; the dashboard can't be served stale; the look-alike's wrong patch is labelled and self-consistent; secrets are kept out of the image;
  an annotated, performed video script; the team dossier; a tested pack builder and the zip; GitHub tracker brought up to date.
- **Open threads:** unchanged from 0009 and still the whole ballgame: **0001#7 live Bob**, 0009#16 Dockerfile unbuilt, 0009#17 human-only submission items. **New:** none.
- **Next session should:** merge the `demo-readiness` PR, then Task A (`scripts/verify_bob.py`). Record the video only from a checkout that has this session's fixes.
- **Stage delta:** none (S4 still BLOCKED on a live call; S6–S9 DONE).
