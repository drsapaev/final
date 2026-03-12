# Wave 2C QR Create-Branch Extraction Status

Date: 2026-03-09
Status: `done`

## Files Changed

- `backend/app/api/v1/endpoints/qr_queue.py`
- `backend/app/services/qr_full_update_queue_assignment_service.py`
- `backend/tests/unit/test_qr_create_branch_extraction.py`
- `backend/tests/characterization/test_qr_queue_direct_sql_characterization.py`
- `backend/tests/characterization/test_qr_queue_direct_sql_concurrency.py`

## Architecture Change

QR additional-service create logic is no longer hidden inline inside
`full_update_online_entry()`.

It now goes through the explicit QR-local seam:

- `prepare_create_branch_handoffs(...)`
- `materialize_create_branch_handoffs(...)`

## Behavior Preservation

Verified unchanged:

- consultation preserves original QR `queue_time`
- additional services still create independent entries
- raw SQL numbering still remains as-is
- `source` inheritance remains `entry.source or "online"`
- same-day QR semantics remain unchanged

## Tests Run

- `cd backend && pytest backend/tests/characterization/test_qr_queue_direct_sql_characterization.py -q -c pytest.ini`
- `cd backend && pytest backend/tests/characterization/test_qr_queue_direct_sql_concurrency.py -q -c pytest.ini`
- `cd backend && pytest tests/unit/test_qr_create_branch_extraction.py -q`
- `cd backend && pytest tests/characterization -q -c pytest.ini`
- `cd backend && pytest tests/test_openapi_contract.py -q`
- `cd backend && pytest -q`

## Results

- QR characterization: passed
- QR concurrency characterization: passed
- QR extraction unit tests: passed
- full characterization suite: passed
- OpenAPI contract: passed
- full backend suite: passed

## Outcome

QR family is closer to boundary migration, but this slice stops at explicit seam
extraction. The correct next step is a dedicated boundary-readiness recheck.
