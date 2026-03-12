## Wave 2D Service Code Drift Fix Status

Date: 2026-03-11
Mode: one-drift-at-a-time, evidence-based

Status: `COMPLETED`

## Scope

- widen `Service.service_code` to fit legitimate current runtime values
- add a narrow schema guard test
- re-run the QR characterization pilot in both DB lanes

## Results

- narrow schema test:
  `pytest tests/unit/test_service_service_code_schema.py -q`
  -> `1 passed`
- SQLite QR characterization family:
  `pytest tests/characterization/test_qr_queue_direct_sql_characterization.py -q -c pytest.ini`
  -> `4 passed`
- Postgres QR characterization family:
  `pytest tests/characterization/test_qr_queue_direct_sql_characterization.py -q -c pytest.ini --db-backend=postgres`
  -> `3 passed, 1 failed`
- OpenAPI:
  `pytest tests/test_openapi_contract.py -q`
  -> `10 passed`
- broader SQLite backend suite confidence run:
  `pytest -q`
  -> `786 passed, 3 skipped`

## Outcome

- the `service_code` length drift is fixed
- SQLite baseline remains green
- Postgres pilot progresses beyond the previous insert-time blocker
- the next remaining blocker is now a bounded `queue_time` timezone-awareness
  mismatch in the same QR characterization family

## Implication

The dual-lane pilot remains trustworthy.

This slice confirms the one-drift-at-a-time workflow:

1. surface real blocker
2. fix that blocker narrowly
3. re-run both lanes
4. expose the next honest blocker without broad churn
