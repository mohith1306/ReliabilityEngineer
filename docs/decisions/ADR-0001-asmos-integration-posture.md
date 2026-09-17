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

**Risk carried forward.** Ownership asymmetry did not emerge organically in ASMOS's corpus.
If it also fails to emerge in real incident history, the routing story weakens to "correct
fallback behaviour," which is defensible but much less compelling. This must be **measured
before S8 is built on it** — thread 0001#8.

## Alternatives rejected

- **`pip install asmos`.** Rejected on startup weight and demo fragility, and because the
  research API is frozen for reproducibility rather than designed for a consumer.
- **Ignore ASMOS; build plain RAG over the repo.** Rejected: it discards the only genuinely
  novel asset the team has, and it is what every competing project will build.
- **Use ASMOS as ARCHITECTURE.md section 8 describes it** (file-relevance ranking).
  Rejected: ASMOS's own README states it does not beat RAG at span retrieval. Using it there
  invites the strongest possible objection while claiming the weakest possible benefit.
