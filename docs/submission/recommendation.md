# Recommendation: four of us, one 3-minute video

The video is one continuous screen recording of the dashboard. **Each of us narrates one part, and that person's image appears when their part starts**,
so a judge can put a face to each voice. The words are the ones in [VIDEO_SCRIPT.md](VIDEO_SCRIPT.md), unchanged. This page says **what each of you is
explaining and why**: the one idea you own, the words to lean on, what is on screen while you talk, what never to say, and the judge question you should
be ready for afterwards.

Rehearse with [demo_walkthrough.html](demo_walkthrough.html): type your names under *Before recording*, press **T** for the timer, and read your part
against the clock.

---

## At a glance

| | Time | Your beats | Words | The one idea you own | Best fit |
|---|---|---|---|---|---|
| **Speaker 1** | 0:00–0:43 (43 s) | The problem · Say what is real · It stops before touching anything | 103 | *Agents write fixes fast. BRE makes them prove it, and nothing is written until a human says so.* | Our clearest, most confident voice: this part decides whether a judge keeps watching |
| **Speaker 2** | 0:43–1:26 (43 s) | A human approves · Fix on a branch, verified 3 ways · The ledger | 103 | *The safety is structural: a key-based approval, its own branch, the real test suite, and every prediction on record.* | Whoever knows the write path (`reliability/remediation/`) best |
| **Speaker 3** | 1:26–2:17 (51 s) | Same failure, from memory · The look-alike | 119 | *It learns who was verifiably right, and it catches itself when a remembered answer is wrong.* | Whoever knows the ASMOS routing best, with a calm voice: this is the strongest moment |
| **Speaker 4** | 2:17–3:00 (43 s) | What it learned + honest numbers · Close | 113 | *We measured it, and we say the limits out loud.* | Whoever can say "nominal" and "made no difference" without sounding apologetic |

The parts are balanced on purpose: 43 to 51 seconds and 103 to 119 words each. That is about 160 words per minute, with the clicking done while talking.

---

## How to use the four images

1. **A small corner card, not a full-screen cut.** Put each photo bottom-left over the screen recording for about **2 seconds** when that person starts,
   with a name and a role underneath (e.g. *Your Name · write path & safety*). The screen is the evidence. Never cover it.
2. **Make the four look like a set.** Same crop (head and shoulders), same size, same position, a plain background, no filters. Cut in and cut out;
   no zooms, spins or slides.
3. **No separate "meet the team" intro.** There is no time: the script is 2:45 of speech in 3:00. The corner card *is* the introduction. Put full names
   and roles in the video description as well.
4. **No "over to you" handoffs.** The script flows as one voice; the new image is the handoff. Record each part separately, with the same microphone at
   the same distance, and level the volume in editing.
5. **Order is fixed.** Speaker 1 → 4 as above; the demo steps only work in this order (the look-alike needs incident 1 resolved first).

---

## Speaker 1 · 0:00–0:43 · "Why this exists, and what is real"

**Image caption:** *Name · problem & product*

**What you are explaining.** The problem in one breath, then honesty about the demo, then the first proof that BRE is careful: it stops before it writes
anything. You set the tone: calm, precise, no hype.

**Say (word for word):**
> AI agents like IBM Bob can write a fix in minutes. The question every team then asks is: was it right, was it safe, and did we learn anything?
>
> In this recording the diagnosing and fixing agent is a labelled stand-in for Bob, and the dashboard says so here. Everything else is real: the git branches, the test runs, the approval gate and the ledger.
>
> BRE gathers evidence, has the agent diagnose it read-only, and scores the risk. Every factor is visible: severity, blast radius, missing tests. It's HIGH, so it stops and waits for a human. Nothing has touched the repository yet.

*Live run instead?* Use the live lines from the script's *If the recording is LIVE* table (the walkthrough's **Live Bob** switch shows them).

**Lean on:** "was it right, was it safe, and did we learn anything" (slow down; these three questions structure the whole video) · "labelled stand-in"
· "**Nothing has touched the repository yet.**" (pause after it).

**On screen while you talk:** title card → dashboard, point at the **SIMULATED BOB** pill → create *Connection pool exhaustion (config regression)* → Run →
it stops at **AWAITING APPROVAL** → open **Risk & approval**.

**Why this part matters to judges:** *Presentation* (a clear problem) and *Application of technology* (Bob's role, stated honestly). Saying "stand-in"
yourself, first, is what makes everything after it believable.

**Never say:** "Bob fixed it" over a simulated run · "AI that never makes mistakes".

**Be ready for:** *"Why is Bob simulated?"* Bob is metered and credential-gated. A public demo, CI, and teammates without a key all need the rest to run.
The stand-in only runs when explicitly switched on, is labelled on every screen, and is flagged in every ledger row. *(If the live run, Task B, is done: say the video is live.)*

---

## Speaker 2 · 0:43–1:26 · "Why the write path can be trusted"

**Image caption:** *Name · write path & safety*

**What you are explaining.** That safety is *built in*, not requested in a prompt. Approval is tied to a key, the fix goes on its own branch after a
checkpoint, the real tests verify it at three levels, and every prediction was written down before anyone knew if it was right.

**Say (word for word):**
> A human approves, and the record stores who it was from their API key. Never a name typed into a form.
>
> The fix lands on its own branch, after a pinned git checkpoint, never on the main branch. The changed files come from git, not from what the agent claims. Then it's verified three ways: the test that was failing, its whole file, and the entire suite. Only then is it called fixed.
>
> Every prediction — the diagnosis, the risk level, the fix — was written down as pending before anyone knew if it was right, and closed only by that test run.

**Lean on:** "from their API key" · "never on the main branch" · "from git, not from what the agent claims" · "**the test that was failing, its whole file,
and the entire suite**" (count them on three beats) · "written down … before anyone knew".

**On screen while you talk:** type `demo-operator-key` → **Approve** → Run → **RESOLVED** → **Patch** (branch, checkpoint, `pool_size: 2 → 20`) →
**Verification** (three levels, all passed) → **Ledger** (four rows, all *confirmed*).

**Why this part matters to judges:** *Business value* (an audit trail for every AI-authored change) and *Originality* (the outcome ledger: predictions
are recorded before they are known, and only a test run closes them).

**Never say:** "it guarantees correctness". Say "a deterministic test-suite exit code decides", which is what it is.

**Be ready for:** *"What stops an agent making the tests pass by deleting them?"* A diff guard on the actual patch rejects deleted test files, net test
removal, skip/xfail markers, `assert True` and CI-config edits, whatever the agent claims, then rolls back and keeps the rejected patch as evidence.
Also *"Can someone fake an approval?"* The identity comes from the key, and a test sends forged names in the body to prove they are ignored. The gate is
re-checked inside the write engine.

---

## Speaker 3 · 1:26–2:17 · "It learns, and it catches its own mistakes"

**Image caption:** *Name · learning & routing (ASMOS)*

**What you are explaining.** The idea that makes this more than a pipeline. A recurring failure is answered from *verified* memory at no agent cost.
Then comes the trap: a look-alike with the same symptom and a different cause. Memory answers, the tests say no, BRE rolls back, and it finds the real
cause. This is the moment judges will remember.

**Say (word for word):**
> Same failure again. This time the diagnosis comes from memory, at zero agent cost, because a passing test suite already vouched for it. It only reuses it because similarity times ownership clears a threshold, and ownership is earned from verified outcomes. That's the ASMOS routing idea.
>
> Now a trap: same symptom, different cause. Memory answers, the patch goes in, and the tests say no. BRE rolls it back, records that diagnosis as refuted, and asks for a new approval. On attempt two it won't reuse that memory for this incident, runs a full investigation, and finds the real cause, a hard cap in the code. The agent was wrong, and the system found out because the tests said so.

**Lean on:** "because a passing test suite already vouched for it" · "**same symptom, different cause**" (pause before and after) · "**the tests say no**" ·
"the system found out because the tests said so" (the last line of your part; let it land).

**On screen while you talk:** incident 2 → **Diagnosis**: *source: memory · 0 tokens*, *similarity 1.00 x ownership 0.42 = 0.42 >= tau 0.30* → the
**LOOK-ALIKE** → Diagnosis (memory, ownership 0.63) → Approve → Run → **Verification failed** → **Patch** *rolled_back* → Approve → Run → **RESOLVED** →
**Diagnosis** attempt 2 finds `min(size, 2)` → **Ledger**: attempt 1 *refuted*, attempt 2 *confirmed*.

**Why this part matters to judges:** *Originality*. Reputation is earned only from verification (the ASMOS mechanism). The system catching its own
wrong answer is the proof, and it is what separates BRE from a cache.

**Never say:** "zero cost" without "agent" · "reverted" (say "rolled back": the patch is kept as evidence) · "it never reuses that memory again". It is
excluded *for this incident* and loses standing (0.63 → 0.54); it is not deleted.

**Be ready for:** *"Isn't this just RAG, or a cache of past fixes?"* A cache reuses an answer whether or not it was right. BRE reuses a diagnosis only
when its ownership, earned from verified outcomes and lost on refutations, clears a threshold, and the look-alike shows it catching a wrong reuse. The
honest nuance: ranking evidence *within* a route is ordinary retrieval. What is new is routing *between sources* on verified reputation.

---

## Speaker 4 · 2:17–3:00 · "The numbers, and their limits"

**Image caption:** *Name · evaluation & results*

**What you are explaining.** That we measured it against the agent alone, on the same incidents, with real git and real tests, and that we say the
limits before anyone asks. Confidence here comes from *not* overselling.

**Say (word for word):**
> Ownership is computed only from verified outcomes. The look-alike cost memory standing. We measured it against the agent alone on the same incidents with real git and real tests. On recurring failures, 6 of 10 diagnoses came from memory, none refuted, about 25% cheaper. With look-alike twins mixed in, the tests refuted 4 of 13 reuses, each was rolled back and retried, and it was still about 10% cheaper, with the same resolution rate. Those costs are nominal while Bob is simulated. And at this scale, ownership evolving over time made no difference, which we report as found.
>
> Bob Reliability Engineer: don't just generate a fix. Verify it, and learn who was right.

**Lean on:** "**6 of 10**" · "**4 of 13**" (say numbers slowly) · "**nominal**" (never skip it) · "which we report as found" · the tagline: pause
before "Verify it".

**On screen while you talk:** **What BRE has learned** (memory 0.542, bob 0.703) → **Evaluation** (slices *recurring* and *full*) → the repository URL.

**Why this part matters to judges:** *Business value* backed by evidence, and credibility. A team that reports its own flat result is believed on the
rest.

**Never say:** "saves 25%" on its own · "it always wins". If your rehearsal runs long, the one sentence you may drop is the last one before the tagline
("And at this scale…"). Keep it for Q&A.

**Be ready for:** *"Aren't those numbers cherry-picked?"* The corpus includes look-alikes on purpose, all slices are reported, the flat result is
stated, and we replaced our own wrong threshold tuner when the measurement contradicted it (ADR-0006). What they *don't* show: real Bob costs,
anything beyond 14 synthetic incidents, or Bob's diagnostic quality.

---

## If "the four images" are your Bob task-session screenshots

The rules require **a Bob task-session screenshot from each team member** (Task C in [BOB_USAGE_PLAN.md](BOB_USAGE_PLAN.md)). They go on the submission
form, and they can also appear in the video: one per speaker, as the corner card instead of a photo. If you use them, each person says one sentence
about **their own** screenshot, and only what it actually shows:

> "I asked Bob, in Ask mode, to review BRE's write path for ways to bypass the approval gate or weaken the tests. It found [what it found], and we turned [that finding] into [the test or fix]."

- Fill the brackets from your own `docs/submission/bob_review_<name>.md`. If Bob found nothing you acted on, say that: "It found nothing we had to change."
- Adding four such sentences costs about 20 seconds. Take it from the demo by showing incident 2 more briefly, **never** from the look-alike or the word "nominal".
- Do not show a screenshot of a session you didn't run, and do not describe the demo's stand-in as one of these sessions.

---

## Delivery, for all four

- **Pace:** about 160 words per minute. Read your part aloud with the walkthrough's timer (press **T**) twice before recording.
- **Pause** after each line in **bold** above. A one-second pause reads as confidence on video.
- **Speak while the screen moves.** Every *Run the loop* takes under 4 seconds, so talk over it; don't wait in silence.
- **Numbers slowly, jargon never unexplained.** If you say "ownership", the next few words say what it means (the script already does this).
- **Same wording as the pill.** If the corner says SIMULATED BOB, never say "Bob did this". It is the one mistake that can't be fixed in Q&A.
