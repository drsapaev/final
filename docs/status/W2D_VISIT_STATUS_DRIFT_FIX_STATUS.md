## Wave 2D Visit Status Drift Fix Status

Date: 2026-03-11
Mode: one-drift-at-a-time, evidence-based

Status: `COMPLETED`

## Scope

- widen `Visit.status` to fit legitimate current runtime values
- add a narrow schema guard test
- re-run the shared `postgres_pilot` marker lane in both DB backends

## Results

- narrow schema test:
  `pytest tests/unit/test_visit_status_schema.py -q`
  -> `1 passed`
- SQLite marker lane:
  `pytest -m postgres_pilot -q -c pytest.ini`
  -> `28 passed, 762 deselected`
- Postgres marker lane:
  `pytest -m postgres_pilot -q -c pytest.ini --db-backend=postgres`
  -> `27 passed, 1 failed, 762 deselected`
- OpenAPI:
  `pytest tests/test_openapi_contract.py -q`
  -> `10 passed`

## Outcome

- the `Visit.status` length drift is fixed
- SQLite marker lane remains green
- Postgres marker lane progresses beyond the previous schema blocker
- the next remaining blocker is now a bounded datetime comparison mismatch in
  the confirmation family

## Implication

This slice confirms the current posture:

1. the shared `postgres_pilot` marker layer is operational
2. the marker lane still surfaces real bounded drift honestly
3. CI wiring is still premature until the current marker lane is fully green
