# Presenting BRE — and answering the hard questions

Judging criteria (from the event page): **Application of Technology** (a *clear* application of IBM Bob 2.0) · **Presentation** · **Business Value** · **Originality**.

## The 30-second version

> AI agents like IBM Bob can write a fix in minutes. But teams can't tell whether it was right, whether it was safe, or whether they learned anything.
> **Bob Reliability Engineer wraps Bob in a safety-and-learning loop.** Bob diagnoses read-only. A human approves. The fix lands on its own git branch and is verified by the real test suite;
> if it fails it's rolled back. And BRE remembers which diagnoses turned out to be *verifiably* right — so a recurring failure is answered from verified memory at zero Bob cost.
> *Don't just generate a fix. Verify it — and learn who was right.*

## The 3-minute story (matches the video script)

1. **Problem, and what is real** (26 s) — the three unanswerable questions; say LIVE or SIMULATED.
2. **Run an incident** (60 s) — it stops at *awaiting approval*; risk shown with every factor; **nothing has touched the repo**; approve with a key; fix on a branch; verified at three levels; ledger says *confirmed*.
3. **Same incident again** (18 s) — diagnosis from **memory at 0 tokens**, with the routing decision shown.
4. **The look-alike** (33 s) — same symptom, different cause; memory answers, **the tests say no**, rolled back, refuted, full investigation finds the real cause. *This is the strongest moment — don't cut it.*
5. **What it learned + honest results** (37 s).
6. **Close** (6 s).

Four speakers? The split, and what each of you says: [recommendation.md](../submission/recommendation.md). Rehearse with [demo_walkthrough.html](../submission/demo_walkthrough.html).

Script with timings: [VIDEO_SCRIPT.md](../submission/VIDEO_SCRIPT.md). Presenter guide and troubleshooting: [DEMO.md](../DEMO.md).

## Say / don't say

| Do say | Don't say |
|---|---|
| "This run uses **[live IBM Bob / a labelled Bob stand-in]** — you can see it in the corner." | "Bob fixed it" about a SIMULATED run |
| "Costs are **nominal** while Bob is simulated; the counts are measured." | "It saves 25% of tokens" without "nominal" |
| "Verification is a **test-suite exit code**, not a model grading itself." | "It's always right" / "it guarantees correctness" |
| "The look-alike shows the system catching its own mistake." | "It never makes mistakes" |
| "We built this with Claude Code and opencode; Bob is the engineering capability BRE orchestrates — and here is where we used Bob: …" | Anything about Bob usage you can't back with a file in the repo |

## Likely questions — with honest answers

**Isn't this just RAG / a cache of past fixes?**
No. A cache reuses an answer whether or not it was right. BRE reuses a diagnosis only when its *ownership* — earned from verified outcomes, lost from refutations — clears a threshold, and the look-alike demo shows the system catching a wrong reuse. Honest nuance: ranking evidence *within* a route is ordinary retrieval, and ASMOS's own README says it doesn't beat RAG at that; the routing between *sources* is what's new.

**Did IBM Bob write this code?**
No — it was built with Claude Code and opencode (the session ledger records which). IBM Bob is the engineering capability BRE orchestrates. **[TEAM: state exactly which Bob sessions you ran and what they produced — Tasks A–D.]**

**Why is Bob simulated in the demo?**
Bob is metered and credential-gated; a public hosted demo, CI and contributors without a key all need the rest of the system to run. The stand-in only runs when explicitly enabled, is labelled on every screen, and flags every ledger row as simulated. **[TEAM: if Task B is done, say the video is live.]**

**How do you know the fix is right?**
Three levels, fail-fast: the test that was failing, its whole file, the entire suite. If nothing was failing before the patch, the fix is *unverifiable* and BRE refuses to call it verified. A run that collected zero tests is never a pass.

**What stops an agent making the tests pass by deleting them?**
A diff guard on the actual patch rejects deleted test files, net test removal, skip/xfail markers, `assert True`, and CI-config edits — regardless of what the agent claims — then rolls back and keeps the rejected patch as evidence.

**Can someone fake an approval?**
Approval identity comes from an API key that resolves to an operator record. A test sends forged names in the request body; they're ignored. The gate is re-checked inside the write engine, so even editing the status column by hand doesn't bypass it.

**What did you actually measure?**
Bob alone vs BRE vs a frozen-ownership ablation, same incidents, real git and pytest. Recurring failures: 6 of 10 from memory, 0 refuted, ~24.8% lower *nominal* cost. With look-alike twins: 13 routed, 4 refuted by the tests, each rolled back and retried, ~10.1% lower nominal cost, identical resolution. Ownership *evolution* made no measurable difference at this scale — we report that as flat. Full report: [RESULTS.md](../RESULTS.md).

**Aren't those numbers cherry-picked?**
Not knowingly: the corpus includes look-alikes on purpose, all slices are reported, and the flat result is stated. We also caught and replaced our own wrong threshold tuner when the measurement contradicted it (ADR-0006). What they *don't* show: real Bob costs, generalisation beyond 14 synthetic incidents (τ is tuned in-sample), or Bob's diagnostic quality.

**What happens on a codebase it has never seen?**
Cold start: no memory, so it falls back to a full Bob investigation. And BRE is read-only unless the repository is explicitly allowlisted.

**What's the business value?**
Fewer wasted agent attempts on failures the team has already solved; an audit trail for every AI-authored change (who approved, what was verified, what was rolled back); and a safe way to let agents act near production because the control is structural, not a request in a prompt.

**What's original here?**
Verification-gated reputation (ASMOS) applied to reliability engineering, with a *deterministic* verifier; treating "the agent was wrong and the system found out" as the headline; and an evaluation that includes the adversarial case and reports its own mistakes.

**Multi-tenant? Scale?**
Not in the MVP — single tenant, one repository at a time — but `tenant_id` and cost fields are on every ledger record from the first write because they can't be backfilled.

**What would you do with more time?**
Run it live end to end with measured cost; evaluate τ out of sample; try a smaller ownership prior so ownership adapts faster at small scale; connect real CI failure feeds; add CI for BRE itself on Linux and macOS.

## Known weak spots — know them before a judge finds them

- **No live Bob call yet** (unless Tasks A–B are done). Own it up front.
- **The Dockerfile was never built** and only Windows has been verified.
- **Small synthetic corpus, in-sample threshold.**
- **Ownership evolution is flat** at this scale.
- The repo was largely built with other AI assistants — say so before someone asks.
