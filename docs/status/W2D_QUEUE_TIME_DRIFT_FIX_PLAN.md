## Scope

Narrow Postgres drift fix for `queue_time` round-trip behavior in:

- [test_qr_queue_direct_sql_characterization.py](C:/final/backend/tests/characterization/test_qr_queue_direct_sql_characterization.py)

This slice is limited to the QR direct-SQL characterization family. It does not change application runtime behavior, global datetime handling, or the broader fixture stack.

## Exact failing assertion

Postgres pilot failure is in:

- `test_qr_direct_sql_characterization_full_update_first_fill_uses_raw_next_number_and_current_time`

Current failing assertion:

- `assert original_entry.queue_time == original_queue_time`

Observed values:

- written `original_queue_time`: naive local datetime from `_local_now()` using `datetime.now(ZoneInfo("Asia/Tashkent")).replace(tzinfo=None)`
- read back under Postgres: aware datetime from `DateTime(timezone=True)` round-trip

## Current model/runtime evidence

- `OnlineQueueEntry.queue_time` is declared as `DateTime(timezone=True)` in [online_queue.py](C:/final/backend/app/models/online_queue.py)
- QR additional-service seam uses aware datetimes from `datetime.now(ZoneInfo("Asia/Tashkent"))` in [qr_full_update_queue_assignment_service.py](C:/final/backend/app/services/qr_full_update_queue_assignment_service.py)
- queue creation path falls back to aware timestamps via `queue_service.get_local_timestamp()` in [queue_service.py](C:/final/backend/app/services/queue_service.py)

## Candidate root cause

This looks like **test expectation/setup drift**, not a new production schema drift:

- the characterization helper `_local_now()` strips timezone info
- the model and queue creation paths are already timezone-aware
- SQLite tolerated the naive helper
- Postgres honestly returns an aware `queue_time` for a timezone-aware column

## Narrowest safe fix strategy

Update the QR characterization family so that its seeded `queue_time` values use aware datetimes consistent with the model/runtime ownership.

Why this is the narrowest honest fix:

- it aligns the test fixture with the declared column semantics
- it does not weaken assertions
- it does not change runtime behavior
- it allows the pilot to keep surfacing real DB drift instead of SQLite-shaped datetime assumptions

## Out of scope

- global datetime normalization across the app
- fixture stack rewrite
- changing queue runtime semantics
- unrelated timezone handling in other families
