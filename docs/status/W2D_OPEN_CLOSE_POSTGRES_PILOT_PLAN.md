## Wave 2D Open/Close Postgres Pilot Plan

Date: 2026-03-10
Mode: pilot-extension, evidence-based

## Target family

- `backend/tests/characterization/test_open_close_day_characterization.py`

## Why this is the next best pilot family

- It is queue/legacy-sensitive but narrower than broader queue integration
  families.
- It exercises the OnlineDay legacy island, `Setting(category="queue")`,
  response snapshots, and broadcast behavior together.
- It is a good second pilot family after allocator characterization because it
  touches a different type of legacy operational behavior without requiring a
  broad fixture rewrite.

## Reused dual-lane harness pieces

- default SQLite lane remains unchanged
- opt-in Postgres lane via `--db-backend=postgres`
- isolated temporary Postgres schema
- connect/checkout schema pinning already added to the pilot engine

## Narrow additions needed

None were required up front.

Plan:

- run the target family in the default SQLite lane
- run the same family in the opt-in Postgres lane
- record any honest drift
- only add harness changes if the family exposes a real blocker

## Out of scope

- broad fixture rewrite
- migration of the whole test stack to Postgres
- any production/runtime behavior changes
- unrelated queue-sensitive families
