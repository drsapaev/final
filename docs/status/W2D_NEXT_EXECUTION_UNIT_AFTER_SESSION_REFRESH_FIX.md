## Next Execution Unit After Session Refresh Fix

Date: 2026-03-10
Mode: pilot-first, evidence-based

## Chosen next step

`A) extend Postgres pilot to another queue-sensitive family`

## Why this is the safest next step

- The target pilot family now passes fully on both SQLite and Postgres lanes.
- The harness approach has proven it can surface real drift without forcing a
  broad fixture rewrite.
- The next highest-value move is to reuse the same staged approach on another
  queue-sensitive family while the current setup is still well-bounded.

## Why other options are not chosen yet

- `B) fix the next newly discovered drift` is not chosen because no new blocker
  remains inside the current pilot family.
- `C) pause and consolidate pilot findings` would add less value than extending
  a now-validated pilot pattern.
- `D) broader fixture-layer prep now justified` is premature because the pilot
  does not currently require broad fixture surgery.

## Exact first slice

Start the next dual-validation pilot on one additional queue-sensitive family,
preferably:

- `backend/tests/characterization/test_open_close_day_characterization.py`

or the next strongest queue/legacy-sensitive characterization family selected by
the existing Postgres test-alignment roadmap.
