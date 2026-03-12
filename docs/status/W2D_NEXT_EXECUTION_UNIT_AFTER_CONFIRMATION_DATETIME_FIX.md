## Next Execution Unit After Confirmation Datetime Fix

Date: 2026-03-11
Mode: one-drift-at-a-time, evidence-based

## Chosen next step

`B) proceed to dedicated CI job wiring for postgres_pilot`

## Why this is the safest next step

- The shared `postgres_pilot` marker layer is now green in both SQLite and
  Postgres lanes.
- The latest bounded drift fixes have removed the remaining blockers in the
  aggregated marker run.
- The pilot strategy is now validated strongly enough to become a regression
  guard instead of remaining only a local/manual tool.

## Why other options are not chosen yet

- `A) fix the next newly discovered pilot drift` is not chosen because the
  current aggregated marker lane has no remaining blocker.
- `C) pause and consolidate marker-lane findings` is less valuable than turning
  the validated marker lane into a durable CI signal.
- `D) broader datetime review now justified` is not needed because the current
  confirmation-family datetime issue was resolved within bounded scope.

## Exact next slice

A dedicated CI job wiring pass for:

- `pytest -m postgres_pilot -q -c backend/pytest.ini --db-backend=postgres`

Why this next:

- it operationalizes the validated marker lane
- it keeps SQLite as the fast default baseline
- it turns the pilot into a durable Postgres regression guard without forcing a
  broad fixture migration
