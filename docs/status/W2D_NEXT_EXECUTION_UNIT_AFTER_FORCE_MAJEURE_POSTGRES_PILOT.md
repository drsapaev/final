## Next Execution Unit After Force Majeure Postgres Pilot

Date: 2026-03-10
Mode: pilot-extension, evidence-based

## Chosen next step

`A) continue pilot to another bounded family`

## Why this is the safest next step

- The pilot is now green on five bounded queue-sensitive families.
- We have repeated evidence that the strategy can distinguish:
  - true DB/schema drift
  - harness/session drift
  - stable no-drift legacy/parity/exceptional families
- Extending one family at a time continues to give the best confidence gain for
  the lowest migration risk.

## Why other options are not chosen yet

- `B) fix a newly discovered drift in force_majeure family` is not chosen
  because no new DB-lane drift was discovered there.
- `C) pause and consolidate pilot findings` would slow a strategy that is still
  producing high-value signal safely.
- `D) broader fixture-layer prep now justified` is still premature because the
  pilot keeps working without broad fixture changes.

## Exact next slice

Extend the same dual-lane pilot to:

- `backend/tests/characterization/test_confirmation_split_flow_concurrency.py`

Why this next:

- it returns to a bounded queue-sensitive concurrency family
- it is more likely to surface transactional or visibility drift than the
  already-stable parity families
- it still fits the same narrow pilot pattern
