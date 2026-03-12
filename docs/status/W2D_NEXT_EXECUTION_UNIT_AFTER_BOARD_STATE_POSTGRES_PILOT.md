## Next Execution Unit After Board State Postgres Pilot

Date: 2026-03-10
Mode: pilot-extension, evidence-based

## Chosen next step

`A) continue pilot to another queue-sensitive family`

## Why this is the safest next step

- The pilot is now green on four different queue-sensitive families.
- We have repeated evidence that the strategy can distinguish:
  - true DB/schema drift
  - harness/session drift
  - stable no-drift legacy/parity families
- Extending one family at a time still gives the highest confidence gain for
  the lowest migration risk.

## Why other options are not chosen yet

- `B) fix a newly discovered drift in board_state family` is not chosen because
  no new DB-lane drift was discovered there.
- `C) pause and consolidate pilot findings` would slow a strategy that is still
  producing high-value signal safely.
- `D) broader fixture-layer prep now justified` is still premature because the
  pilot keeps working without broad fixture changes.

## Exact next slice

Extend the same dual-lane pilot to:

- `backend/tests/characterization/test_force_majeure_allocator_characterization.py`

Why this next:

- it remains queue/legacy-sensitive
- it touches the isolated exceptional-domain path that already exposed source
  semantics earlier
- it is still small and characterization-oriented, so it fits the same narrow
  pilot pattern
