## Wave 2D Confirmation Datetime Drift Fix Status

Date: 2026-03-11
Mode: one-drift-at-a-time, evidence-based

Status: `COMPLETED`

## Scope

- add confirmation-local datetime normalization
- fix confirmation write/compare paths only
- add narrow validation
- re-run the shared `postgres_pilot` marker lane in both DB backends

## Results

- narrow confirmation datetime tests:
  `pytest tests/unit/test_confirmation_datetime.py -q`
  -> `2 passed`
- SQLite marker lane:
  `pytest -m postgres_pilot -q -c pytest.ini`
  -> `28 passed, 764 deselected`
- Postgres marker lane:
  `pytest -m postgres_pilot -q -c pytest.ini --db-backend=postgres`
  -> `28 passed, 764 deselected`
- OpenAPI:
  `pytest tests/test_openapi_contract.py -q`
  -> `10 passed`

## Outcome

- the confirmation-family naive-vs-aware datetime mismatch is fixed
- SQLite marker lane remains green
- Postgres marker lane is now also green
- the shared `postgres_pilot` marker layer is ready to move toward CI guardrail
  wiring

## Implication

This slice closes the current bounded-drift loop for the aggregated pilot lane.

The next safest step is no longer another drift fix. The next safest step is:

- dedicated CI job wiring for `postgres_pilot`
