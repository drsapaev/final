## Wave 2D DailyQueue.specialist_id FK Drift Fix Status

Date: 2026-03-10
Status: `COMPLETED`

## What was fixed

- `DailyQueue.specialist_id` ownership is now consistently treated as
  `doctors.id`
- registrar batch queue creation resolves specialist identity to canonical
  `doctor.id`
- legacy `get_or_create_daily_queue(...)` now canonicalizes compatible
  `user_id` input to `doctor.id`
- queue-sensitive fixtures/tests were aligned so the broader SQLite suite stays
  stable

## Verification

- narrow validation tests:
  - `pytest tests/unit/test_daily_queue_specialist_schema.py tests/unit/test_confirmation_reuse_existing_entry.py tests/unit/test_registrar_batch_allocator_boundary.py -q`
  - result: `8 passed`
- SQLite pilot family:
  - `pytest tests/characterization/test_queue_allocator_characterization.py tests/characterization/test_queue_allocator_concurrency.py -q -c pytest.ini`
  - result: `7 passed`
- Postgres pilot family:
  - `pytest tests/characterization/test_queue_allocator_characterization.py tests/characterization/test_queue_allocator_concurrency.py -q -c pytest.ini --db-backend=postgres`
  - result: `6 passed, 1 failed`
- OpenAPI:
  - `pytest tests/test_openapi_contract.py -q`
  - result: `10 passed`
- full backend suite:
  - `pytest -q`
  - result: `785 passed, 3 skipped`

## Remaining blocker

The Postgres pilot now stops only at the separate `session.refresh(user)`
concurrency issue. That blocker is intentionally left for the next slice.
