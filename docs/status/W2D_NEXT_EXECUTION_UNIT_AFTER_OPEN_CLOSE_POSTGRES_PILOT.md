## Next Execution Unit After Open/Close Postgres Pilot

Date: 2026-03-10
Mode: pilot-extension, evidence-based

## Chosen next step

`A) continue pilot to another queue-sensitive family`

## Why this is the safest next step

- The allocator characterization/concurrency family is green on both lanes.
- The open/close characterization family is also green on both lanes.
- We now have positive evidence that the dual-lane pilot approach can both:
  - surface real drift when it exists
  - confirm stable behavior when no DB-specific drift exists

## Why other options are not chosen yet

- `B) fix a newly discovered drift in open/close family` is not chosen because
  no new SQLite-vs-Postgres drift was discovered there.
- `C) pause and consolidate pilot findings` would slow down a strategy that is
  currently proving safe and informative.
- `D) broader fixture-layer prep now justified` is still premature because the
  current pilot method remains effective without broad fixture surgery.

## Exact next slice

Extend the same dual-lane pilot to another queue/legacy-sensitive family,
preferably:

- `backend/tests/characterization/test_queues_stats_parity_harness.py`

This keeps the next step close to the OnlineDay legacy island while staying
smaller and lower-risk than broader queue integration families.
