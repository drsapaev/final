## Wave 2D Source Length Drift Fix Status

Date: 2026-03-10  
Status: `SUCCESS`

## Fixed blocker

Resolved the Postgres-invalid length mismatch for:

- `queue_entries.source`
- current runtime value: `force_majeure_transfer`

The column now uses `String(24)` in
[online_queue.py](C:/final/backend/app/models/online_queue.py).

## Validation

### Narrow schema guard

- `pytest tests/unit/test_queue_entry_source_schema.py -q`
- Result: `1 passed`

### SQLite pilot baseline

- `pytest tests/characterization/test_queue_allocator_characterization.py tests/characterization/test_queue_allocator_concurrency.py -q -c pytest.ini`
- Result: `7 passed`

### Postgres pilot

- `pytest tests/characterization/test_queue_allocator_characterization.py tests/characterization/test_queue_allocator_concurrency.py -q -c pytest.ini --db-backend=postgres`
- Result: `5 passed, 2 failed`

### OpenAPI

- `pytest tests/test_openapi_contract.py -q`
- Result: `10 passed`

### Full backend confidence run

- `pytest -q`
- Result: `783 passed, 3 skipped`

## Outcome

- The `force_majeure_transfer` blocker is gone.
- The Postgres pilot progressed further.
- The next blockers are now:
  - `DailyQueue.specialist_id` strict FK enforcement
  - one Postgres-lane session/refresh issue
