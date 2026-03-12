## Exact mismatch

The Postgres pilot for:

- [test_qr_queue_direct_sql_characterization.py](C:/final/backend/tests/characterization/test_qr_queue_direct_sql_characterization.py)

surfaced a `queue_time` round-trip mismatch in:

- `test_qr_direct_sql_characterization_full_update_first_fill_uses_raw_next_number_and_current_time`

The failing assertion used raw object equality:

- `original_entry.queue_time == original_queue_time`

Observed behavior:

- SQLite read back the seeded `queue_time` as a naive `datetime`
- Postgres read back the same stored value as an aware `datetime` for `DateTime(timezone=True)`

## Classification

This was **expectation drift**, not a new application schema drift.

Evidence:

- `OnlineQueueEntry.queue_time` is declared as `DateTime(timezone=True)` in [online_queue.py](C:/final/backend/app/models/online_queue.py)
- QR runtime creation paths already use aware timestamps in [qr_full_update_queue_assignment_service.py](C:/final/backend/app/services/qr_full_update_queue_assignment_service.py) and [queue_service.py](C:/final/backend/app/services/queue_service.py)
- the failing characterization case seeds a legacy-style `queue_time` manually and checks preservation of the stored value, not end-user timezone semantics

## Narrow fix applied

The fix stayed inside the characterization family:

- restored the file-local `_local_now()` helper to its previous naive behavior so QR token expiry setup remains unchanged
- added `_queue_time_wall_clock(...)` in [test_qr_queue_direct_sql_characterization.py](C:/final/backend/tests/characterization/test_qr_queue_direct_sql_characterization.py)
- changed the failing assertion to compare preserved wall-clock value rather than raw naive-vs-aware object identity

This is the narrowest honest fix because the test is characterizing preservation of the original stored QR `queue_time`, not enforcing a global timezone normalization contract.

## Result

After the fix:

- SQLite lane passes for the QR direct-SQL characterization family
- Postgres lane also passes for the same family
- no new QR-family blocker surfaced in this slice
