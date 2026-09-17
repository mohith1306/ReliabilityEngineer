"""The outcome ledger -- prediction in, verified outcome out. Stage S3.

The substrate everything else learns from and is measured by. See ADR-0003 for why
this exists and why it is built before Bob integration.

Contract:
    record.py    OutcomeLedger.open(prediction) -> OutcomeRecord   (status=pending)
                 OutcomeLedger.close(record_id, status, verification_run_id)
    query.py     Accuracy, calibration and cost rollups per source, per topic,
                 per risk level -- the inputs to ARCHITECTURE.md section 30.

Invariants:
    - Only `reliability.verification` may call close().
    - A record is opened at prediction time, never reconstructed afterwards.
    - tenant_id and cost fields are populated from the first write even while the
      MVP is single-tenant (ERRATA A7, A8) -- neither can be backfilled.
"""
