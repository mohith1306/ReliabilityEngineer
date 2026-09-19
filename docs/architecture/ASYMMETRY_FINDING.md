# Ownership Asymmetry in Real Repositories — measured

**Thread 0001#8. Result: NO-GO on every repository tested.**

The ASMOS routing story needs some sources to be reliably better than others on some
components. ASMOS found asymmetry does **not** emerge organically in its own constructed
corpus. [ADR-0001](../decisions/ADR-0001-asmos-integration-posture.md) carried that
forward as a risk to measure before stage S8 was built on it. This is the measurement.

- **Method:** claim events from [`connectors/git.py`](../../connectors/git.py) (a merged
  commit is a verified claim by its author on the topics its files touch), fed into
  `asmos.e6.asymmetry` **unmodified**. Using the reference implementation is the point —
  the metric must not be something BRE invented to flatter itself.
- **Criterion:** ASMOS's own pre-registered bar — OCI ≥ 0.70 **and** p < 0.001 against an
  agent-label permutation null (B=1000, seed=42).
- **Reproduce:** `venv/Scripts/python.exe scripts/measure_asymmetry.py`
- **Artifact:** `docs/artifacts/asymmetry_20260919_154301.json`

---

## Results

| Repository | Contributors | Commits | Topics | Claims | **OCI** | **Null mean** | p | Verdict |
|---|---|---|---|---|---|---|---|---|
| ASMOS | 4 | 226 | 29 | 351 | 0.862 | 0.813 | 0.033 | **NO-GO** |
| Dental capstone | 2 | 249 | 25 | 468 | 0.767 | 0.731 | 0.103 | **NO-GO** |
| PAY *(control)* | 1 | 60 | 19 | 150 | 1.000 | 1.000 | 1.000 | **NO-GO** |
| BRE | 2 | ~40 | 11 | 15 | 0.924 | 0.929 | 0.715 | **NO-GO** |

## What the numbers say

**The OCI looks impressive and means nothing.** Read the observed column alone and every
repo looks strongly owned — 0.77 to 1.00, all above the 0.70 bar. Read it beside the null
and the effect evaporates: random reassignment of author labels produces almost exactly
the same concentration. ASMOS observed 0.862 against a null of 0.813. BRE's observed 0.924
is **below** its null of 0.929 — negative z.

**High OCI is a small-team artifact.** With four contributors, the top agent holds a large
share of any topic by arithmetic, not by ownership. The permutation null is designed to
catch exactly this, and it did.

**The negative control validates the instrument.** PAY has one author: OCI is exactly
1.000, the null is exactly 1.000, p = 1.0. Perfect apparent concentration carrying zero
information. That is the correct behaviour and it is the clearest illustration of why the
raw OCI must never be quoted on its own.

**Zero refutation events. In any repository.** 852 commits across four repos and not one
`Revert "..."` commit. The upstream prototype models a detected revert as the refutation
signal; in real history that signal does not occur at all. The verified/refuted loop
cannot be fed from git history, because git history is almost entirely "verified."

**A prediction of mine failed, and it is worth recording.** Before running this I expected
unresolved author identities to materially understate concentration — one person split
across several agent ids spreads their claims and lowers the top share. The direction was
right (ASMOS resolves to 4 people from 17 name/email pairs, and raw names give 5 apparent
agents) but the magnitude was negligible: 0.862 either way. The aliased identities were
low-volume contributors. The identity resolution in `connectors/git.py` is still correct
and still worth having — it just did not rescue this result, and claiming otherwise would
be exactly the kind of confident nonsense the evidence rule exists to prevent.

---

## What it means — and why it is not fatal

The honest headline is that **this proxy was the wrong question**, and the measurement is
what makes that visible rather than arguable.

Commit authorship measures *who writes the code*. The routing mechanism needs *who is
verifiably right about a component*. Those are different quantities, and only the second
one is what ASMOS's ownership score is defined over. A contributor can author most of a
subsystem and still be the wrong source to ask about why it is failing.

More decisively: **BRE's agents are not humans.** They are diagnosis sources — IBM Bob, a
prior incident, a static analyzer, possibly a specific human pulled from blame. Asymmetry
among *those* cannot be measured from commit history at all, because commit history
contains none of them.

So the result does not say "the ASMOS angle does not work." It says something more useful:

> The signal BRE needs does not exist in git history. BRE has to **generate** it.

That is precisely what the lifecycle already does. Every verification run produces a
verified-or-refuted outcome against a diagnosis source — a deterministic test-suite exit
code, not an LLM judging itself, and not a `Revert` commit that never gets written. The
outcome ledger ([ADR-0003](../decisions/ADR-0003-outcome-ledger.md)) is the place that
signal accumulates.

This strengthens rather than weakens the argument in
[ASMOS_INTEGRATION.md](ASMOS_INTEGRATION.md): git history has essentially no refutation
signal (0 reverts in 852 commits), while BRE manufactures refutation on every failed
verification. BRE is not mining a signal that was already there — it is creating one that
was not.

## Consequences for the plan

1. **Do not build S8 on the assumption that asymmetry emerges from contribution history.**
   It was measured and it does not. Ownership must be learned from BRE's own outcome
   ledger, not bootstrapped from git blame.
2. **A git-derived ownership prior is not worthless, but it must not be claimed as
   evidence.** If used at all it is a cold-start prior, and the fact that it is
   indistinguishable from chance at small N has to be stated wherever it appears.
3. **The demo corpus must be built so that asymmetry can be observed.** ASMOS constructed
   its corpus deliberately and said so in its README. BRE needs ≥10 seeded incidents
   (already an S3 exit criterion) spread across components such that different sources
   genuinely differ in accuracy — otherwise routing correctly falls back to global search
   every time, which is right behaviour and a dull demo.
4. **Never quote an OCI without its null.** On this data the raw number would have
   supported a confident and completely false claim in four out of four repositories.

## Limitations

- **The test has almost no statistical power here.** One to four agents is far too few.
  A repository with 50+ contributors could plausibly show genuine asymmetry, and that
  experiment was not run — no such repo was available locally. This is the decisive
  follow-up if a git-derived prior is ever wanted.
- **Topic granularity is a free parameter.** Topics are derived from directory structure;
  a different partition would produce different numbers. It was not swept.
- **Four repositories, three of them small, all from one author's account.** This is not
  a sample anyone should generalise from. It is sufficient to refute "asymmetry will
  obviously be there," which is what it was run to test.
- **`is_accepted` is true for every merged commit.** These repositories commit directly to
  the mainline, so "merged" carries no review signal. In a repo with enforced PR review the
  claim event would be meaningfully stronger.
