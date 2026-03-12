## Next Execution Unit After QR Characterization Postgres Pilot

Date: 2026-03-11
Mode: pilot-extension, evidence-based

## Chosen next step

`B) fix a newly discovered drift in qr_queue family`

## Why this is the safest next step

- The pilot already did its job: it exposed one concrete, bounded blocker.
- The surfaced issue is narrow and honest:
  `Service.service_code` length enforcement under Postgres.
- Fixing that specific blocker preserves the one-drift-at-a-time discipline that
  has kept the pilot trustworthy.

## Why other options are not chosen yet

- `A) continue pilot to another bounded family` is not chosen because the
  current QR characterization family still has one unresolved Postgres blocker.
- `C) pause and consolidate pilot findings` would slow progress while the next
  blocker is already well-localized.
- `D) broader fixture-layer prep now justified` is still premature because this
  slice found a bounded schema issue, not a broad harness failure.

## Exact next slice

A narrow drift-fix pass for:

- `Service.service_code` length / ownership expectations surfaced by
  `backend/tests/characterization/test_qr_queue_direct_sql_characterization.py`

Why this next:

- it is the exact blocker preventing the Postgres lane from completing this
  family
- it stays within the same bounded QR/service characterization context
- it does not require broad fixture migration
