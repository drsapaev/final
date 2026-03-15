## Next Execution Unit After QR Postgres Pilot

Date: 2026-03-11
Mode: pilot-extension, evidence-based

## Chosen next step

`A) continue pilot to another bounded family`

## Why this is the safest next step

- The pilot is now green on eight bounded queue-sensitive families.
- We have repeated evidence that the strategy can distinguish:
  - true DB/schema drift
  - harness/session drift
  - stable no-drift legacy/parity/concurrency families
- Extending one family at a time continues to provide the best confidence gain
  for the lowest migration risk.

## Why other options are not chosen yet

- `B) fix a newly discovered drift in qr_queue family` is not chosen because no
  new DB-lane drift was discovered there.
- `C) pause and consolidate pilot findings` would slow a strategy that is still
  producing high-value signal safely.
- `D) broader fixture-layer prep now justified` is still premature because the
  pilot keeps working without broad fixture changes.

## Exact next slice

Extend the same dual-lane pilot to:

- `backend/tests/characterization/test_qr_queue_direct_sql_characterization.py`

Why this next:

- it stays in the same QR direct-SQL area while complementing the concurrency
  family with characterization-level behavior checks
- it remains bounded and lower-risk than broader queue integration flows
- it continues the same narrow pilot pattern
