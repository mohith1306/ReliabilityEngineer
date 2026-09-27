# Demo video script — 3:00, annotated and checked

Every beat below has five parts: **what is on screen**, **what to say** (word for word), **why the beat exists**, **the source** that makes
the sentence true, and **how it was checked**. A sentence without a source is not in this script.

*Checked* means the flow was performed end to end in the dashboard (demo mode, simulated Bob, `BRE_TAU=0.30`) on 2026-09-27 and the
on-screen text was copied from the page; the numbers were compared with the artifacts and the tests named. Three bugs were found by doing this and are
fixed on `main` (PR #14; see *What checking the script found*, at the end). **Record from `main`.**

**Rehearse with [demo_walkthrough.html](demo_walkthrough.html)**: this script as a click-through page, with the dashboard's exact on-screen text for every
step, a timer, and a Simulated/Live switch. With the demo running, open **<http://127.0.0.1:8000/walkthrough>** and switch *On screen* to
**Real dashboard**: the working dashboard sits beside your lines, and the page warns if its LIVE/SIMULATED wording disagrees with the server.
Who says which part: [recommendation.md](recommendation.md).

---

## Before you press record (5 minutes)

| # | Do this | Why |
|---|---|---|
| 1 | Start the dashboard: `powershell -ExecutionPolicy Bypass -File scripts\run_demo.ps1` (macOS/Linux: `scripts/run_demo.sh`). Open <http://127.0.0.1:8000> | `-ExecutionPolicy Bypass` avoids Windows' "running scripts is disabled" error on a fresh machine |
| 2 | Press **Ctrl+F5** once | Makes sure the browser runs the current dashboard, not a cached copy |
| 3 | Press **Reset** | The demo database (`bre.db`) survives restarts. Without a reset, old incidents and old memory change what the look-alike does |
| 4 | Decide: **LIVE** or **SIMULATED**. Check the pill in the top-right corner says the same | The one mistake that cannot be recovered in Q&A is saying "Bob did this" over a SIMULATED run |
| 5 | 1080p, browser zoom ~110%, dark theme (◐ button). Close other tabs. Mute notifications | Readability on a judge's laptop |
| 6 | Do one full dry run, then **Reset** again | Steps must run in this order: the look-alike only shows a refutation if the first incident was resolved first |

**Timing.** Each slot is sized to its words at about 160 words per minute, with the clicking done *while* talking (every Run takes under 4 s). An earlier version gave the results beat 20 s for 98 words; if a rehearsal still runs long, the one sentence you may drop is the last one of the results beat ("And at this scale, ownership evolving…"): keep it for Q&A instead.

**Order is load-bearing:** Incident 1 (*Connection pool exhaustion (config regression)*) → Incident 2 (the same) → Incident 3 (*LOOK-ALIKE*).
Each **Run the loop** click takes under 4 s locally.

---

## The script

### 0:00–0:12 · The problem

- **On screen:** Title card (slide 1 of `docs/submission/BRE_pitch.html`, or `docs/submission/cover.png`).
- **Say:** "AI agents like IBM Bob can write a fix in minutes. The question every team then asks is: was it right, was it safe, and did we learn anything?"
- **Why:** Presentation criterion; names the three questions the rest of the video answers, in order.
- **Source:** Problem statement, `README.md`; `docs/team-pack/01_WHAT_WE_BUILT.md` ("The problem").
- **Checked:** Opinion/framing, no factual claim.

### 0:12–0:26 · Say what is real

- **On screen:** The dashboard. Point at the pill, top right: **SIMULATED BOB** (or **LIVE IBM BOB**).
- **Say (simulated):** "In this recording the diagnosing and fixing agent is a labelled stand-in for Bob, and the dashboard says so here. Everything else is real: the git branches, the test runs, the approval gate and the ledger."
- **Say (live, only if the pill says LIVE):** "This run uses live IBM Bob. Everything you'll see is real: Bob, git, the test suite, the gate, the ledger."
- **Why:** Rule 1 of the team pack. Judges will see the pill; saying it first turns a weakness into credibility.
- **Source:** Pill text from `apps/api/settings.py:47` (`"label": "SIMULATED BOB"`); the orange banner on every incident tab says "Everything else is real: the git checkpoint and branch, the pytest runs, the verification levels, the rollback and the outcome ledger."
- **Checked:** In the browser. Test: `test_system_endpoint_says_bob_is_simulated_and_what_is_writable` (`tests/integration/test_api_loop.py`).

### 0:26–0:43 · Incident 1: it stops before touching anything

- **On screen:** Scenario **Connection pool exhaustion (config regression)** → **Create demo incident** → **▶ Run the loop**. The status chips stop at **AWAITING APPROVAL**; the message reads *"4 step(s): investigate → diagnose → assess_risk → request_approval. HIGH risk: waiting for an authenticated operator to approve"*. Open **Risk & approval**.
- **Say:** "BRE gathers evidence, has the agent diagnose it read-only, and scores the risk. Every factor is visible: severity, blast radius, missing tests. It's HIGH, so it stops and waits for a human. Nothing has touched the repository yet."
- **Why:** Application of technology and safety. Shows the approval gate *before* any write, and that the score is auditable (non-negotiable §4.3: every score stores its components).
- **Source:** Factor table from `reliability/risk/classifier.py:51-70` (each factor stored with its input and points); gate `reliability/orchestration/gate.py`, re-checked inside the write engine at `reliability/remediation/engine.py:116`. On screen: *Risk HIGH · score 4 · approval required*; factors (input → points): severity high → 2, database migration false → 0, api surface affected false → 0, blast radius 2 → 1, tests available partial → 1, low confidence 0.86 → 0; *Thresholds: {"CRITICAL":7,"HIGH":4,"MEDIUM":2}*.
- **Checked:** In the browser. Test: `test_full_lifecycle_over_http_with_an_authenticated_human_approval` asserts exactly these 4 steps and `blocked_on == "approval"`.

### 0:43–0:53 · A human approves, with a key

- **On screen:** Type the key into the **operator API key** box (the demo shows it under the button: `demo-operator-key`) → **Approve**. Message: *"Approved. Run the loop to continue."*
- **Say:** "A human approves, and the record stores who it was from their API key. Never a name typed into a form."
- **Why:** Business value (audit trail) and safety (approval can't be forged).
- **Source:** `apps/api/routes/approvals.py:50` (`operator = auth.authenticate(db, authorization)`); stored name comes from the operator record (`approvals.py:60`), not the body.
- **Checked:** In the browser (after the fix below). Test: the same lifecycle test sends forged `operator_name`/`approved_by` in the body and asserts they're ignored; wrong or missing key → 401.

### 0:53–1:14 · The fix, on its own branch, verified three ways

- **On screen:** **▶ Run the loop** → **RESOLVED**; message *"3 step(s): approved → remediate → verify. incident is RESOLVED"*. Open **Patch**: branch `bre/<id>/attempt-1`, checkpoint `<sha> on master`, *Changed (from git)* `config/app.yaml`, diff `pool_size: 2` → `pool_size: 20`. Then open **Verification**: **targeted** (the tests that were red) passed · **component** (their whole files) passed · **regression** (the entire suite) passed.
- **Say:** "The fix lands on its own branch, after a pinned git checkpoint, never on the main branch. The changed files come from git, not from what the agent claims. Then it's verified three ways: the test that was failing, its whole file, and the entire suite. Only then is it called fixed."
- **Why:** The core product claim. Verification is a test-suite exit code, not a model grading itself.
- **Source:** Checkpoint ref `reliability/remediation/git_ops.py:139-141` (`refs/bre/checkpoints/…`); branch-only rule `git_ops.py:10`; changed files from `git diff --name-only` at `git_ops.py:105,172`; the three levels at `reliability/verification/verifier.py:137-176` (a later level is skipped if an earlier one fails).
- **Checked:** In the browser. Test: the lifecycle test asserts `changed_files == ["config/app.yaml"]`, a `bre/` branch, levels `["targeted","component","regression"]`, and the diff `-  pool_size: 2` / `+  pool_size: 20`.

### 1:14–1:26 · The ledger

- **On screen:** **Ledger** tab. Four rows for attempt 1: routing, diagnosis, risk level, remediation plan. All **confirmed**, *closed by* **verification-engine**. Footnote: "* nominal (simulated agent)".
- **Say:** "Every prediction — the diagnosis, the risk level, the fix — was written down as pending before anyone knew if it was right, and closed only by that test run."
- **Why:** Originality. The outcome ledger is what makes the learning honest (ADR-0003; non-negotiable §4.4).
- **Source:** Pending on creation `reliability/ledger/record.py:101`; closed only by verification `record.py:168` (`close_for_verification`). The tab's own caption says the same.
- **Checked:** In the browser. Test: the lifecycle test asserts every outcome is `confirmed` and carries a `verification_run_id`.

### 1:26–1:44 · Incident 2: the same failure, answered from memory

- **On screen:** Same scenario → **Create demo incident** → **▶ Run the loop** → open **Diagnosis**: *source: memory · confidence 0.86 · 0 tokens* and *Routing: similarity 1.00 x ownership 0.42 = 0.42 >= tau 0.30*. (Optional: approve and run → RESOLVED.)
- **Say:** "Same failure again. This time the diagnosis comes from memory, at zero agent cost, because a passing test suite already vouched for it. It only reuses it because similarity times ownership clears a threshold, and ownership is earned from verified outcomes. That's the ASMOS routing idea."
- **Why:** Business value (cost of recurring failures) and originality (verification-gated reputation, not a cache).
- **Source:** Routing score and threshold `asmos_bridge/routing/router.py:12-13`; ownership = 0.6 × Trust + 0.4 × Share `asmos_bridge/ownership/trust.py:54`; Trust = (7 + correct)/(10 + total) `trust.py:26-30`. Formulas are pinned to the real ASMOS source by 95 parity tests (`tests/unit/test_asmos_parity.py`).
- **Checked:** In the browser. Test: `test_the_second_similar_incident_is_answered_from_memory_and_ownership_shows_it` asserts `("memory", 0)` and `ROUTE` with `tau 0.30`.
- **Do not say** "zero cost" without "agent", and do not say "Bob" here if the pill says SIMULATED.

### 1:44–2:17 · Incident 3: the look-alike (do not cut this)

- **On screen:** Scenario **Connection pool exhaustion (LOOK-ALIKE: the cause is in code)** → Create → Run. **Diagnosis** shows *source: memory* and *ownership 0.63* (it rose after incident 2 was verified). Approve → Run. The message shows 7 steps ending in *request_approval*: the fix was applied, **Verification** reads *failed · targeted: 1 of 1 previously failing test(s) still fail*, component and regression *skipped*. **Patch**, attempt 1: *rolled_back*, summary ending *"(applied to a repository it does not fit)"*. Approve again → Run → **RESOLVED**. **Diagnosis**, attempt 2: *source: bob-adapter* and *"ConnectionPool.__init__ in dbpool.py clamps the pool with min(size, 2)…"*, routing reason *"every candidate memory was already tried on this incident and failed verification"*. **Ledger**: attempt 1 rows **refuted**, attempt 2 **confirmed**.
- **Say:** "Now a trap: same symptom, different cause. Memory answers, the patch goes in, and the tests say no. BRE rolls it back, records that diagnosis as refuted, and asks for a new approval. On attempt two it won't reuse that memory for this incident, runs a full investigation, and finds the real cause, a hard cap in the code. The agent was wrong, and the system found out because the tests said so."
- **Why:** Strongest moment. It shows the safety loop catching a plausible wrong answer, which is what separates this from a cache or plain RAG.
- **Source:** Exclusion `reliability/orchestration/routed.py:15` and `asmos_bridge/routing/router.py:105`; rollback `reliability/remediation/git_ops.py:191` (the rejected patch kept under `refs/bre/failed/*`); new approval required per attempt `reliability/orchestration/gate.py`; attempt cap `reliability/orchestration/loop.py:12-13` (default 3).
- **Checked:** In the browser. Test: `test_a_lookalike_is_refuted_over_http_and_the_incident_recovers` asserts refuted memory, `rolled_back`, `attempt == 2`, the misapplied label and diff, and predictors `["memory", "bob-adapter"]`.
- **Say "rolled back", not "reverted".** The patch is kept as evidence.

### 2:17–2:54 · What it learned, and the honest numbers

- **On screen:** **What BRE has learned**: memory's ownership fell to **0.542** and bob's is **0.703**. Then **Evaluation**: slice *recurring* (10 incidents) and slice *full* (14 incidents, 4 look-alikes).
- **Say:** "Ownership is computed only from verified outcomes. The look-alike cost memory standing. We measured it against the agent alone on the same incidents with real git and real tests. On recurring failures, 6 of 10 diagnoses came from memory, none refuted, about 25% cheaper. With look-alike twins mixed in, the tests refuted 4 of 13 reuses, each was rolled back and retried, and it was still about 10% cheaper, with the same resolution rate. Those costs are nominal while Bob is simulated. And at this scale, ownership evolving over time made no difference, which we report as found."
- **Why:** Business value with evidence, and the limits said out loud before a judge raises them.
- **Source:** `docs/artifacts/comparison_recurring_*.json` (6.0 from memory, 0 refuted, −24.8% nominal); `docs/artifacts/comparison_full_20260926T210746Z.json` (13.0 from memory, 4.0 refuted, 4.0 wasted attempts, −10.1% nominal, resolution identical); ablation flat (same file, `bre_frozen` arm). Summary in `docs/RESULTS.md`.
- **Checked:** Numbers copied from the Evaluation tab and matched to the artifact files. Ownership values from the learned tab: 0.6·(7.5/11) + 0.4·(1/3) = 0.542.
- **Must say "nominal"** (rule 2). Do not say "saves 25%" on its own.

### 2:54–3:00 · Close

- **On screen:** Repository URL <https://github.com/mohith1306/ReliabilityEngineer>, tagline.
- **Say:** "Bob Reliability Engineer: don't just generate a fix. Verify it, and learn who was right."
- **Why:** Memorable close; the URL is what judges click.
- **Checked:** The repository is public.

---

## Spoken track only (for a separate voice recording: 438 words, about 2:45 at ~160 words per minute)

> AI agents like IBM Bob can write a fix in minutes. The question every team then asks is: was it right, was it safe, and did we learn anything?
>
> In this recording the diagnosing and fixing agent is a labelled stand-in for Bob, and the dashboard says so here. Everything else is real: the git branches, the test runs, the approval gate and the ledger.
>
> BRE gathers evidence, has the agent diagnose it read-only, and scores the risk. Every factor is visible: severity, blast radius, missing tests. It's HIGH, so it stops and waits for a human. Nothing has touched the repository yet.
>
> A human approves, and the record stores who it was from their API key. Never a name typed into a form.
>
> The fix lands on its own branch, after a pinned git checkpoint, never on the main branch. The changed files come from git, not from what the agent claims. Then it's verified three ways: the test that was failing, its whole file, and the entire suite. Only then is it called fixed.
>
> Every prediction — the diagnosis, the risk level, the fix — was written down as pending before anyone knew if it was right, and closed only by that test run.
>
> Same failure again. This time the diagnosis comes from memory, at zero agent cost, because a passing test suite already vouched for it. It only reuses it because similarity times ownership clears a threshold, and ownership is earned from verified outcomes. That's the ASMOS routing idea.
>
> Now a trap: same symptom, different cause. Memory answers, the patch goes in, and the tests say no. BRE rolls it back, records that diagnosis as refuted, and asks for a new approval. On attempt two it won't reuse that memory for this incident, runs a full investigation, and finds the real cause, a hard cap in the code. The agent was wrong, and the system found out because the tests said so.
>
> Ownership is computed only from verified outcomes. The look-alike cost memory standing. We measured it against the agent alone on the same incidents with real git and real tests. On recurring failures, 6 of 10 diagnoses came from memory, none refuted, about 25% cheaper. With look-alike twins mixed in, the tests refuted 4 of 13 reuses, each was rolled back and retried, and it was still about 10% cheaper, with the same resolution rate. Those costs are nominal while Bob is simulated. And at this scale, ownership evolving over time made no difference, which we report as found.
>
> Bob Reliability Engineer: don't just generate a fix. Verify it, and learn who was right.

## If the recording is LIVE (Task B done)

- Use these lines instead of the simulated ones. Everything not listed stays word for word. A blanket "the agent" → "Bob" swap would make two lines untrue:
  the comparison was run with the stand-in, and in the look-alike the wrong answer was a *reused* diagnosis, not a fresh one from Bob.

  | Beat | Live line |
  |---|---|
  | 0:12 | "This run uses live IBM Bob. Everything you'll see is real: Bob, git, the test suite, the gate, the ledger." |
  | 0:26 | "…has **Bob** diagnose it read-only…" |
  | 0:53 | "…not from what **Bob** claims…" |
  | 1:26 | "…at zero **Bob** cost…" |
  | 1:44 | last sentence: "**The reused diagnosis was wrong**, and the system found out because the tests said so." |
  | 2:17 | keep "against the agent alone"; replace the nominal sentence with "**Those comparison costs are nominal: that evaluation ran with the stand-in, not live Bob.**" |
- Token counts become measured, not nominal, **for that run only**. The Evaluation numbers stay nominal (they were produced with the stand-in).
- Bob's diagnosis wording will differ from the text quoted above. Read what is on screen, not this script.
- A live run takes minutes, not seconds: cut the waits in editing and say so in the description ("waiting time cut").
- If Bob errors, the dashboard shows the message (HTTP 503). Stop and record SIMULATED instead. **Never** mix a live start with a simulated finish.

## If something goes wrong while recording

| Symptom | Cause | Fix |
|---|---|---|
| Approve shows an error like `[object Object]` or a 422 | The browser is running a cached copy of the old dashboard | Ctrl+F5 (fixed in PR #14: the page is now served `no-cache`) |
| The look-alike is answered by a full investigation and resolves first time | Incident 1 wasn't resolved first, or the database was reset in between | Reset, then run 1 → 2 → 3 in order |
| Old incidents or odd ownership numbers | `bre.db` kept state from an earlier session | Reset |
| "this incident is already being advanced" | Run clicked twice | Wait for *Working…* to finish; it is harmless (HTTP 409) |
| `running scripts is disabled on this system` | Windows execution policy | `powershell -ExecutionPolicy Bypass -File scripts\run_demo.ps1` |
| Port 8000 in use | Another server running | `.\scripts\run_demo.ps1 -Port 8010` |

## What checking the script found (all fixed on `main`, PR #14)

1. **Approve failed in the browser** with `[object Object]`. The dashboard's `api()` helper let the caller's `headers` replace the merged ones, so the approval call (the only one sending `Authorization`) lost `Content-Type` and got a 422. The API tests use a proper client and could not see this. Fixed in `apps/web/index.html`; pinned by `test_the_dashboard_api_helper_keeps_content_type_when_an_authorization_header_is_passed`.
2. **A cached old dashboard kept running the bug after the fix.** `/` is now served with `Cache-Control: no-cache` (`apps/api/main.py`); asserted in `test_the_dashboard_is_served_at_the_root`.
3. **On the look-alike, the Patch tab contradicted itself on camera**: the summary said "Restore … to 20" while the diff showed `20 → 200`. The stand-in's `find: "pool_size: 2"` matched inside `pool_size: 20`. It now matches whole tokens only (`reliability/remediation/executors.py`, `_token_starts`), so the labelled *"(applied to a repository it does not fit)"* path runs and the diff is `20 → 40`. The outcome and every measured number are unchanged: the cap is in code, so either wrong edit fails the same test. Pinned in `test_a_lookalike_is_refuted_over_http_and_the_incident_recovers`.

## Do-nots

- Do not describe a SIMULATED run as Bob's work.
- Do not show the operator key of a real deployment. (The demo key is public by design and says so.)
- Do not quote a token saving without "nominal" unless the run was live and measured.
- Do not skip the look-alike: it is the strongest evidence that the safety story is real.
- Do not say "it never makes mistakes". The video's best moment is the system catching its own mistake.
