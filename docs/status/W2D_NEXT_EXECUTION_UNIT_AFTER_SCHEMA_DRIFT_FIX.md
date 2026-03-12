## Next Execution Unit After Schema Drift Fix

Date: 2026-03-10  
Mode: pilot-first, evidence-based

## Chosen next step

`B) fix the next discovered schema drift`

## Exact next slice

Narrow Postgres schema/value fix for:

- `queue_entries.source`
- current `force_majeure_transfer` value exceeding `VARCHAR(20)`

## Why this is the safest next step

- The original bootstrap mismatch is fixed.
- The Postgres pilot now progresses into runtime behavior and exposes the next
  concrete blocker honestly.
- The `source` length mismatch is narrower and less ambiguous than the
  `DailyQueue.specialist_id` path, which mixes test data and domain ownership
  assumptions.

## Why other options are not chosen yet

- Continuing immediately without another fix would just fail on the same newly
  surfaced blocker.
- A broader fixture/schema alignment pass is still premature because the pilot
  is successfully revealing issues one at a time.
- Human review is not needed yet for the `source` length mismatch because it is
  a concrete schema/value incompatibility, not a semantics dispute.
