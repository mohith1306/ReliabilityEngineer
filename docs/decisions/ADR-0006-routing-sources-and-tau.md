# ADR-0006 — What is routed, what "similar" means, and how tau is chosen

- **Status:** Accepted
- **Date:** 2026-09-27
- **Session:** [0009](../memory/sessions/0009-reconcile-and-build-s6-s9.md)
- **Builds on:** [ADR-0001](ADR-0001-asmos-integration-posture.md), [ADR-0003](ADR-0003-outcome-ledger.md); consequence of the
  measurement in [ASYMMETRY_FINDING.md](../architecture/ASYMMETRY_FINDING.md)

## Context

ADR-0001 adopted ASMOS's mechanism (verification-gated ownership, tau-gated routing with a global-search fallback) and left
open *what* the "agents" and "topics" are in a system where nothing in git history identifies who diagnosed what. Session 0008
measured that git-derived ownership is indistinguishable from chance and that git holds zero refutation events. Ownership has
to be learned from BRE's own ledger or not at all.

## Decision

1. **The routed choice is between two ways to get a diagnosis:** reuse a diagnosis a passing test suite already vouched for
   (`memory`, free) or run a full investigation with Bob (ASMOS's `GLOBAL_SEARCH`, expensive, correct by construction). The
   routing score is ASMOS's, unchanged: `Sim(q, best memory in T) x Ownership(memory, T)`, routed iff `>= tau`. A cold start
   (no memory in the topic) falls back to Bob by construction.
2. **Ownership is computed only from ledger closures backed by a real verification run.** `OwnershipTable.from_ledger` joins
   `outcome_records` to `verification_runs`; it excludes `eval:` closures, pending, abandoned, class-C claims and non-diagnosis
   records. No git history is read anywhere in `asmos_bridge/` (AST-tested).
3. **"Similar" means "same failure signature"**, not "similarly worded": the incident's analysed keywords plus the tokens of the
   failing test ids found in its CI/test evidence. Reports of one failure are phrased differently; the failing test and error
   text are what recur.
4. **tau is tuned by simulating the actual routing policy, on expected net saving.** A correct reuse saves one diagnosis
   (`save`); a wrong one wastes a whole remediation attempt (`waste`), so reuse pays only when precision exceeds
   `waste / (save + waste)` (0.58 on the cassette costs). `asmos_bridge/routing/simulate.py` replays the real decision rule --
   the single best memory, the same signature cosine, ASMOS ownership evolving as outcomes accrue, a refuted memory excluded from
   the retry -- over many random orderings and picks the tau with the highest mean net saving (ties toward the stricter tau).
   "Never route" is a legitimate outcome when no tau pays. The simulator is **validated against the measured end-to-end runs**:
   `scripts/tune_tau.py` re-simulates every committed comparison artifact and reports the agreement (9 of 9 orderings matched
   exactly on memory-served and memory-refuted counts when it was introduced). The router resolves tau as env override -> tuned
   artifact -> labelled ASMOS default, and records which.

   **Rejected, and why this is written down:** tuning on independent (memory, incident) pairs, first with Youden's J and then
   with a utility objective. Both returned a useless or wrong answer -- J = 0.05 ("route almost always"), and then "never route" --
   for a corpus on which the end-to-end harness showed routing *wins* (13 reuses, 4 refuted, ~10% lower nominal cost). The pair
   model scores every memory against every incident; the router consults only the best match, in sequence, with ownership
   evolving. The proxy was mis-specified and the harness caught it. The lesson is to tune the policy that runs, and to validate any
   proxy against the measurement before believing it.
5. **The evaluation includes look-alikes on purpose** (same symptom text and failing test, different cause), reports slices
   separately, and includes a frozen-ownership ablation (ASMOS's own single-variable ablation).

## Consequences

- **Measured, not assumed** (`docs/RESULTS.md`): three scenarios, each with its own tuned tau -- failures that recur; a corpus
  with look-alike twins; and a tau tuned on the first and deployed on the second (out of distribution). Token figures are nominal
  while Bob is simulated. See RESULTS.md for the numbers; do not quote them without the caveats it carries.
- **Similarity cannot separate a look-alike from a true match** when they share a failing test. That is not a bug to tune away: it
  is the reason verification exists. The trust update then lowers the memory's ownership.
- **Ownership evolution is too slow to matter at this scale.** With ASMOS's prior strength of 10 (`alpha=7, beta=3`), one refutation
  moves trust by ~0.03, so the frozen-ownership ablation is flat on a 14-incident corpus. ASMOS's own integration doc predicted
  this. A smaller prior would adapt faster but breaks parity with ASMOS's frozen spec, so it is an explicit future experiment, not
  a quiet tweak.
- tau tuned and evaluated on the same 14 incidents is **in-sample**. It demonstrates the mechanism; it is not a generalisation claim.
