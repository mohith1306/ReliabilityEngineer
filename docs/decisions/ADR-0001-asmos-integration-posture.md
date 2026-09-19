# ADR-0001 — ASMOS Integration Posture

- **Status:** Accepted
- **Date:** 2026-09-17
- **Session:** [0001](../memory/sessions/0001-asmos-alignment-and-workflow.md)

## Context

BRE's architecture document names ASMOS as its context engine but describes something
different from what ASMOS is: a relevance ranker over repository files, rather than a
verification-gated ownership router over agents. See [ERRATA A1](../architecture/ERRATA.md).

ASMOS is a real, audited research artifact with published-quality discipline: stamped
artifacts, seeded runs, single-variable ablations, an evidence ledger, and at least one
honestly reported null result. It is also heavy (chromadb, scikit-learn, optionally a ~2GB
torch stack) and explicitly organised for reproducers rather than consumers.

Three postures were available: ignore ASMOS, depend on it as a package, or vendor a bridge.

## Decision

1. **Use ASMOS's mechanism, corrected** — verification-gated ownership routing over
   diagnosis *sources*, not file-relevance ranking.
2. **Do not take a package dependency.** Re-implement the pure math in `asmos_bridge/`,
   shaped so the real package can be swapped in behind the same interfaces.
3. **Assert parity by test**, not by intention: `tests/unit/test_asmos_parity.py` pins the
   bridge to reference values from the ASMOS implementation.
4. **Name the directory `asmos_bridge/`, never `asmos/`** — the real package is importable
   as `asmos` and a local package of that name shadows it.
5. **Attribute and caveat.** ASMOS's numbers are cited as ASMOS results. Its stated
   limitations (single model, N=5, non-organic asymmetry, FLAT convergence null) travel
   with them.

## Consequences

**Positive.** The demo starts in seconds with no model download. BRE's verification signal
is a test-suite exit code — deterministic, and strictly stronger than the LLM-judged
grading ASMOS itself flags as a limitation. The project inherits a genuine research
mechanism rather than reinventing a weaker one, and inherits the evaluation discipline
along with it.

**Negative.** Two implementations of the same equations will drift unless the parity test
is maintained. Re-implementation forfeits ASMOS's Chroma-backed semantic store, so BRE
needs its own similarity path. Nothing in ASMOS's *results* transfers automatically — BRE
must earn its own numbers on its own corpus.

**Risk carried forward — now MEASURED, and it did not hold.** Session 0004 ran ASMOS's
unmodified asymmetry metrics over four real repositories. Every one is NO-GO against the
pre-registered criterion: observed OCI is high (0.77–1.00) but statistically
indistinguishable from an agent-label permutation null, because high concentration is an
artifact of having very few contributors. See
[ASYMMETRY_FINDING.md](../architecture/ASYMMETRY_FINDING.md).

This does not invalidate the decision above. It relocates the signal: **ownership must be
learned from BRE's own outcome ledger, not bootstrapped from contribution history.** Commit
authorship measures who writes a subsystem, not who is verifiably right about it — and
BRE's agents are diagnosis sources that appear in no commit history at all. Git history
also contains **zero refutation events** (0 reverts in 852 commits), while BRE manufactures
refutation on every failed verification. The signal BRE needs does not exist in git; BRE
creates it.

## Alternatives rejected

- **`pip install asmos`.** Rejected on startup weight and demo fragility, and because the
  research API is frozen for reproducibility rather than designed for a consumer.
- **Ignore ASMOS; build plain RAG over the repo.** Rejected: it discards the only genuinely
  novel asset the team has, and it is what every competing project will build.
- **Use ASMOS as ARCHITECTURE.md section 8 describes it** (file-relevance ranking).
  Rejected: ASMOS's own README states it does not beat RAG at span retrieval. Using it there
  invites the strongest possible objection while claiming the weakest possible benefit.
