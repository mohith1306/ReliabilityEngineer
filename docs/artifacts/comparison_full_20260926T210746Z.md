# BRE vs Bob alone — slice `full`

_Generated 2026-09-26T21:07:46+00:00 · corpus `a96fcf892b75` · 14 incidents (4 look-alikes) · 3 ordering(s) · tau 0.058 (tuned:tau_tuning_full_20260926T205245Z.json) · Bob: **replay**_

## Findings

Over 3 ordering(s) of the corpus:
- Resolution rate: identical between BRE and Bob alone
- Nominal token cost per incident: BRE 10.1% lower (-1019 +/- 27 tokens/incident vs Bob alone). NOMINAL cost model, see note.
- Wasted (failed) attempts: BRE 4.0 vs Bob alone 0.0 per run (paired difference +4.0).
- BRE served 13.0 diagnoses from verified memory per run and had 4.0 refuted by the test suite.
- Ablation (ownership frozen at its prior): 4.0 refuted reuses per run vs 4.0 with ownership evolving. No difference: on this corpus ownership evolution did not change behaviour. Reported as found.
- Token figures are NOMINAL when Bob is replayed (bob/cassettes/*.json: usage_is_simulated=true). Reuse, refutation, attempt and resolution counts are measured; token totals are those counts times a placeholder price, not a measurement of IBM Bob.

## Per arm (mean ± std across orderings)

| arm | resolution | tokens/incident (nominal) | Bob diagnoses | memory diagnoses | refuted reuses | wasted attempts |
|---|---|---|---|---|---|---|
| baseline | 100.0% ± 0.0 | 10071 ± 0 | 14.0 | 0.0 | 0.0 | 0.0 |
| bre | 100.0% ± 0.0 | 9052 ± 27 | 5.0 | 13.0 | 4.0 | 4.0 |
| bre_frozen | 100.0% ± 0.0 | 9052 ± 27 | 5.0 | 13.0 | 4.0 | 4.0 |

## Limits

- Token figures are NOMINAL when Bob is replayed (bob/cassettes/*.json: usage_is_simulated=true). Reuse, refutation, attempt and resolution counts are measured; token totals are those counts times a placeholder price, not a measurement of IBM Bob.
- The corpus is small and synthetic (3 fixture repositories). Look-alike incidents are included on purpose.
- Approvals are automated by the harness; a real run needs a human operator at the gate.
- Verification is a real pytest run in a real git checkout; the diagnosing/fixing agent is a labelled stand-in unless `--bob live` was used.
