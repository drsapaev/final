## Wave 2D QR Characterization Postgres Pilot Status

Date: 2026-03-11
Mode: pilot-extension, evidence-based

Status: `COMPLETED_WITH_REAL_DRIFT`

## Scope

Target family:

- `backend/tests/characterization/test_qr_queue_direct_sql_characterization.py`

## Outcome

- SQLite lane succeeded
- Postgres lane surfaced one bounded schema/test-data drift
- no new harness or fixture changes were required in this slice

## Results

- SQLite lane:
  `pytest tests/characterization/test_qr_queue_direct_sql_characterization.py -q -c pytest.ini`
  -> `4 passed`

- Postgres lane:
  `pytest tests/characterization/test_qr_queue_direct_sql_characterization.py -q -c pytest.ini --db-backend=postgres`
  -> `3 passed, 1 failed`

- OpenAPI:
  `pytest tests/test_openapi_contract.py -q`
  -> `10 passed`

## Drift summary

Postgres rejected a `services.service_code` insert with a value longer than the
declared `String(10)` limit.

The QR characterization family therefore uncovered a real bounded schema drift,
not a harness/session problem.

## Implication

The dual-lane pilot strategy remains trustworthy.

The safest next move is a narrow follow-up on the newly surfaced
`Service.service_code` length drift before extending the same family further.
