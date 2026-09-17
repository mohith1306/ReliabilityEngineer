# ADR-0003 — The Outcome Ledger

- **Status:** Accepted
- **Date:** 2026-09-17
- **Session:** [0001](../memory/sessions/0001-asmos-alignment-and-workflow.md)

## Context

ARCHITECTURE.md section 30 commits to measuring Root Cause Accuracy, Verification Success
Rate, Regression Rate and Context Rediscovery Rate. Section 9 commits to learning "only from
verified outcomes." Section 4.6 makes that a principle.

**None of it is possible with the current schema.** `DiagnosisDB` records a root cause and a
confidence and never records whether it was right. `RiskAssessmentDB` records a level and
never records whether the level was appropriate in hindsight. There is no table connecting
a prediction to its eventual outcome.

The system therefore produces predictions it can never grade. Every accuracy metric in
section 30 is uncomputable, and the ASMOS ownership mechanism — whose entire input is
`(verified_correct, verified_total)` per source per topic — has nothing to consume.

This is not a missing feature. It is a missing **substrate**, and everything the project
claims as differentiated sits on top of it.

## Decision

Introduce a first-class `OutcomeRecord` that closes the loop between a prediction and its
verified result. It lives in `reliability/ledger/`.

**Every prediction writes a record at the moment it is made**, with `status=pending`:

| Prediction | Predicted by | Closed by |
|---|---|---|
| Diagnosis / root cause | Bob, or another diagnosis source | verification result |
| Risk level | risk classifier | whether remediation caused a regression or rollback |
| Routing decision | ASMOS bridge router | whether the routed source produced a verified fix |
| Remediation plan | Bob | test suite |

**Only verification closes a record** — `pending` to `confirmed`, `refuted`, or `abandoned`.
Nothing else may write the terminal state. This is ASMOS Invariant 3, enforced structurally
rather than by convention.

Each record carries, at minimum:

```
id, tenant_id, incident_id, predictor_id (the source), topic,
prediction_type, prediction_payload, claim_class (A/B/C),
predicted_at, confidence, components (the score breakdown - Invariant 8),
status (pending|confirmed|refuted|abandoned),
closed_at, closed_by, verification_run_id,
cost_tokens, cost_wall_ms, attempt_number
```

`tenant_id` and `cost_*` are carried from day one even though the MVP is single-tenant and
cost is not yet claimed — both are impossible to backfill (ERRATA A7, A8).

## Consequences

**Positive.** Section 30's metrics become computable. The ASMOS ownership loop gets its
input. The evaluation harness has something to read. Cost claims become possible because
tokens are recorded at prediction time rather than reconstructed. Risk calibration becomes
measurable: "we said HIGH 40 times and 31 of those really did regress" is a far stronger
demo line than a risk badge on a screen.

**Negative.** Every engine now has a write obligation at prediction time, which is friction
on every code path. Records left `pending` forever are a silent failure mode and need a
sweeper. Storage grows per prediction rather than per incident.

**Ordering.** This moves the ledger to stage **S3**, ahead of Bob integration. Building it
later would leave every incident before it unlabelled, and the corpus is small enough that
losing the early incidents would matter.

## Alternatives rejected

- **Add a `verified` boolean to `DiagnosisDB`.** Rejected: it only covers diagnoses, leaves
  risk and routing ungraded, and has nowhere to put cost, components, or attempt number.
- **Derive outcomes at read time from incident status.** Rejected: `RESOLVED` tells you the
  incident closed, not which of three competing hypotheses was the correct one, and not
  which routing decision earned it.
- **Defer until after the demo works.** Rejected: predictions made before the ledger exists
  are permanently unlabelled. In a corpus of ten to thirty incidents, throwing away the
  first ten is most of the evidence.
