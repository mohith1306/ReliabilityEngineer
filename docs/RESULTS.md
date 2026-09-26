# Results — BRE vs Bob alone

_Generated 2026-09-26T21:21:09+00:00 by `scripts/build_results.py` from the stamped artifacts in `docs/artifacts/`. Every number below is copied from them._

## Read this first

- **Token figures are NOMINAL.** Bob is replaced by a labelled replay stand-in whose cassettes carry placeholder token costs. **Measured** (real git + real pytest + the real ledger): whether each incident resolved, how many attempts it took, how many diagnoses came from memory vs Bob, how many memory reuses the test suite **refuted**, and how many attempts that wasted. Token totals are those counts × a placeholder price: an accounting of the counts, not a measurement of IBM Bob.
- **The corpus is small and synthetic** (14 incidents over 3 fixture repositories, ordering-shuffled 3 times), and tau is tuned **in-sample**. This demonstrates a mechanism. It is not a generalisation claim.
- **Approvals are automated by the harness**; a real run has a human at the gate.
- **Look-alikes are included on purpose.** A router evaluated only on easy cases proves nothing.
- Flat and negative results are reported as found.

## Failures that recur

10 incidents, two fixtures. No look-alikes: every incident that resembles a past one really is that failure again. tau was tuned on this same slice (in-sample).

`10` incidents · `0` look-alikes · `3` orderings · tau `0.2344` (`tuned:tau_tuning_recurring_20260926T205235Z.json`) · Bob: **replay**

| arm | resolution | tokens / incident (nominal) | Bob diagnoses | from memory | refuted reuses | wasted attempts |
|---|---|---|---|---|---|---|
| Bob alone | 100% ± 0.0 | 9900 ± 0 | 10.0 | 0.0 | 0.0 | 0.0 |
| BRE | 100% ± 0.0 | 7440 ± 0 | 4.0 | 6.0 | 0.0 | 0.0 |
| BRE, ownership frozen (ablation) | 100% ± 0.0 | 7440 ± 0 | 4.0 | 6.0 | 0.0 | 0.0 |

**Findings** (generated from the numbers):

Over 3 ordering(s) of the corpus:
- Resolution rate: identical between BRE and Bob alone
- Nominal token cost per incident: BRE 24.8% lower (-2460 +/- 0 tokens/incident vs Bob alone). NOMINAL cost model, see note.
- Wasted (failed) attempts: BRE 0.0 vs Bob alone 0.0 per run (paired difference +0.0).
- BRE served 6.0 diagnoses from verified memory per run and had 0.0 refuted by the test suite.
- Ablation (ownership frozen at its prior): 0.0 refuted reuses per run vs 0.0 with ownership evolving. No difference: on this corpus ownership evolution did not change behaviour. Reported as found.
- Token figures are NOMINAL when Bob is replayed (bob/cassettes/*.json: usage_is_simulated=true). Reuse, refutation, attempt and resolution counts are measured; token totals are those counts times a placeholder price, not a measurement of IBM Bob.

_Artifact: `docs/artifacts/comparison_recurring_20260926T205900Z.json`_

## A corpus with look-alike twins

14 incidents. Four of them are look-alikes of earlier ones: the same symptom text and the same failing test, but the cause is a hard-coded cap in code while the config is healthy. Similarity cannot tell them apart. tau was tuned on this corpus (in-sample).

`14` incidents · `4` look-alikes · `3` orderings · tau `0.058` (`tuned:tau_tuning_full_20260926T205245Z.json`) · Bob: **replay**

| arm | resolution | tokens / incident (nominal) | Bob diagnoses | from memory | refuted reuses | wasted attempts |
|---|---|---|---|---|---|---|
| Bob alone | 100% ± 0.0 | 10071 ± 0 | 14.0 | 0.0 | 0.0 | 0.0 |
| BRE | 100% ± 0.0 | 9052 ± 27 | 5.0 | 13.0 | 4.0 | 4.0 |
| BRE, ownership frozen (ablation) | 100% ± 0.0 | 9052 ± 27 | 5.0 | 13.0 | 4.0 | 4.0 |

**Findings** (generated from the numbers):

Over 3 ordering(s) of the corpus:
- Resolution rate: identical between BRE and Bob alone
- Nominal token cost per incident: BRE 10.1% lower (-1019 +/- 27 tokens/incident vs Bob alone). NOMINAL cost model, see note.
- Wasted (failed) attempts: BRE 4.0 vs Bob alone 0.0 per run (paired difference +4.0).
- BRE served 13.0 diagnoses from verified memory per run and had 4.0 refuted by the test suite.
- Ablation (ownership frozen at its prior): 4.0 refuted reuses per run vs 4.0 with ownership evolving. No difference: on this corpus ownership evolution did not change behaviour. Reported as found.
- Token figures are NOMINAL when Bob is replayed (bob/cassettes/*.json: usage_is_simulated=true). Reuse, refutation, attempt and resolution counts are measured; token totals are those counts times a placeholder price, not a measurement of IBM Bob.

_Artifact: `docs/artifacts/comparison_full_20260926T210746Z.json`_

## Out of distribution: tau tuned without look-alikes, deployed where they exist

The same 14 incidents, but tau comes from the recurring-only tuning. This is what happens if the threshold was tuned on clean history and then met a look-alike.

`14` incidents · `4` look-alikes · `3` orderings · tau `0.2344` (`tuned:tau_tuning_recurring_20260926T205235Z.json`) · Bob: **replay**

| arm | resolution | tokens / incident (nominal) | Bob diagnoses | from memory | refuted reuses | wasted attempts |
|---|---|---|---|---|---|---|
| Bob alone | 100% ± 0.0 | 10071 ± 0 | 14.0 | 0.0 | 0.0 | 0.0 |
| BRE | 100% ± 0.0 | 9052 ± 27 | 5.0 | 13.0 | 4.0 | 4.0 |
| BRE, ownership frozen (ablation) | 100% ± 0.0 | 9052 ± 27 | 5.0 | 13.0 | 4.0 | 4.0 |

**Findings** (generated from the numbers):

Over 3 ordering(s) of the corpus:
- Resolution rate: identical between BRE and Bob alone
- Nominal token cost per incident: BRE 10.1% lower (-1019 +/- 27 tokens/incident vs Bob alone). NOMINAL cost model, see note.
- Wasted (failed) attempts: BRE 4.0 vs Bob alone 0.0 per run (paired difference +4.0).
- BRE served 13.0 diagnoses from verified memory per run and had 4.0 refuted by the test suite.
- Ablation (ownership frozen at its prior): 4.0 refuted reuses per run vs 4.0 with ownership evolving. No difference: on this corpus ownership evolution did not change behaviour. Reported as found.
- Token figures are NOMINAL when Bob is replayed (bob/cassettes/*.json: usage_is_simulated=true). Reuse, refutation, attempt and resolution counts are measured; token totals are those counts times a placeholder price, not a measurement of IBM Bob.
- **Identical to the previous slice.** On this corpus a wide range of tau values routes exactly the same incidents, so a threshold tuned on clean history would have behaved the same here. Reported as found.

_Artifact: `docs/artifacts/comparison_full_tau_from_recurring_20260926T211646Z.json`_

## How tau was chosen

tau is derived from data (`scripts/tune_tau.py`), never hardcoded. The tuner **simulates the actual routing policy** — the single best memory, ASMOS ownership evolving with verified outcomes, a refuted memory excluded from the retry — over many random orderings, and picks the tau with the highest mean net saving. The simulator is validated against the measured end-to-end runs above. (An earlier pair-based tuner returned *"never route"* for the look-alike corpus, where the harness then showed routing wins; it was wrong and was replaced — see [ADR-0006](decisions/ADR-0006-routing-sources-and-tau.md).)

- **recurring**: tau = `0.2344` maximises mean net saving (`25400` nominal tokens over `50` orderings; `6.0` reuses, `0.0` refuted). Simulator vs measured end-to-end runs: **9 of 9** orderings agree exactly (`scripts/validate_simulator.py`). `docs/artifacts/tau_tuning_recurring_20260926T205235Z.json`
- **full**: tau = `0.058` maximises mean net saving (`9564` nominal tokens over `50` orderings; `13.9` reuses, `4.9` refuted). Simulator vs measured end-to-end runs: **9 of 9** orderings agree exactly (`scripts/validate_simulator.py`). `docs/artifacts/tau_tuning_full_20260926T205245Z.json`
  - 8 (query, memory) pairs are look-alikes with an **identical** failure signature to a true match: similarity alone cannot separate them.

## What this does and does not show

**Shows:** verified memory turns recurring failures into cheaper incidents; the test suite catches a wrong reuse, the patch is rolled back and nothing is left behind; every outcome is recorded against a real verification run; a threshold can be tuned from data and checked against measurement.

**Does not show:** anything about IBM Bob's diagnostic quality (the agent is a stand-in); real token costs; that the threshold generalises to other codebases; or that ownership evolution helps — at ASMOS's prior strength (α+β = 10) one refutation moves trust by about 0.03, so on 14 incidents the frozen-ownership ablation is flat. A smaller prior would adapt faster but breaks parity with ASMOS's frozen spec, so it is an explicit future experiment.

## Reproduce

```bash
python scripts/tune_tau.py --slice recurring --exclude-repo connection_cap
python scripts/tune_tau.py --slice full --latest
python -m reliability.evaluation.compare --slice recurring --exclude-repo connection_cap --tau-artifact docs/artifacts/tau_tuning_recurring_*.json --orderings 3
python -m reliability.evaluation.compare --slice full --tau-artifact docs/artifacts/tau_tuning_full_*.json --orderings 3
python scripts/validate_simulator.py
python scripts/build_results.py
```

Add `--bob live` (with Bob Shell installed and `BOB_API_KEY` set) for **measured** tokens.
