## Next Execution Unit After Service Code Drift Fix

Date: 2026-03-11
Mode: one-drift-at-a-time, evidence-based

## Chosen next step

`B) fix the next newly discovered drift`

## Why this is the safest next step

- The `service_code` blocker is resolved and no longer obscures the family.
- The QR characterization Postgres lane now fails on one clearly bounded next
  issue:
  timezone-aware `queue_time` round-trip behavior.
- This keeps the pilot disciplined and easy to trust.

## Why other options are not chosen yet

- `A) continue to another bounded family` is not chosen because this family
  still has one localized Postgres blocker.
- `C) pause and consolidate pilot findings` would interrupt a clean,
  high-signal progression.
- `D) broader fixture-layer prep now justified` is still premature because the
  newly exposed issue is specific and bounded, not evidence of a broad harness
  failure.

## Exact next slice

A narrow QR characterization drift-fix pass for:

- `queue_time` timezone-awareness / datetime round-trip expectations in
  `backend/tests/characterization/test_qr_queue_direct_sql_characterization.py`

Why this next:

- it is the only blocker left in this family's Postgres lane
- it is clearly narrower than a broad fixture or datetime migration
- it keeps the pilot moving one honest blocker at a time
