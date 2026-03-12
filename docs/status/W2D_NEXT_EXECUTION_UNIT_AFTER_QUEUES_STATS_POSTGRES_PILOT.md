## Next Execution Unit After Queues Stats Postgres Pilot

Date: 2026-03-10
Mode: pilot-extension, evidence-based

## Chosen next step

`A) continue pilot to another queue-sensitive family`

## Why this is the safest next step

- The pilot is now green on three different queue-sensitive families.
- We have evidence that the strategy can:
  - surface real drift
  - surface harness/session issues
  - confirm no DB-specific drift when behavior is stable
- Continuing one family at a time still gives the best confidence gain for the
  lowest risk.

## Why other options are not chosen yet

- `B) fix a newly discovered drift in queues.stats family` is not chosen because
  no new drift was discovered here.
- `C) pause and consolidate pilot findings` would slow a strategy that is still
  producing high-value signal safely.
- `D) broader fixture-layer prep now justified` is still premature because the
  pilot continues to work without broad fixture changes.

## Exact next slice

Extend the same dual-lane pilot to:

- `backend/tests/characterization/test_board_state_parity_harness.py`

Why this next:

- it stays close to the same OnlineDay/legacy read-model area
- it is still bounded and characterization-oriented
- it can further validate whether legacy board-facing parity behavior is stable
  across both DB lanes
