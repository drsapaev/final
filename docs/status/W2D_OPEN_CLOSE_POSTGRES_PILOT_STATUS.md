## Wave 2D Open/Close Postgres Pilot Status

Date: 2026-03-10
Mode: pilot-extension, evidence-based

Status: `COMPLETED`

## Scope

Target family:

- `backend/tests/characterization/test_open_close_day_characterization.py`

## Outcome

- SQLite lane succeeded
- Postgres lane succeeded
- no new harness change was required for this family

## Results

- SQLite lane:
  `pytest tests/characterization/test_open_close_day_characterization.py -q -c pytest.ini`
  -> `3 passed`

- Postgres lane:
  `pytest tests/characterization/test_open_close_day_characterization.py -q -c pytest.ini --db-backend=postgres`
  -> `3 passed`

- OpenAPI:
  `pytest tests/test_openapi_contract.py -q`
  -> `10 passed`

## Drift summary

No SQLite-vs-Postgres drift was observed in this family.

The family continues to document legacy operational split-state behavior, but
that behavior reproduced consistently in both lanes.

## Implication

The multi-family pilot strategy is now validated more strongly and can safely
extend to another queue-sensitive family.
