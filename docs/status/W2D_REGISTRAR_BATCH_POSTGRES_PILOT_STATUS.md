## Wave 2D Registrar Batch Postgres Pilot Status

Date: 2026-03-11
Mode: pilot-extension, evidence-based

Status: `COMPLETED`

## Scope

Target family:

- `backend/tests/characterization/test_registrar_batch_allocator_concurrency.py`

## Outcome

- SQLite lane succeeded
- Postgres lane succeeded
- no additional harness or fixture changes were required

## Results

- SQLite lane:
  `pytest tests/characterization/test_registrar_batch_allocator_concurrency.py -q -c pytest.ini`
  -> `2 passed`

- Postgres lane:
  `pytest tests/characterization/test_registrar_batch_allocator_concurrency.py -q -c pytest.ini --db-backend=postgres`
  -> `2 passed`

- OpenAPI:
  `pytest tests/test_openapi_contract.py -q`
  -> `10 passed`

## Drift summary

No SQLite-vs-Postgres drift was observed in this family.

The family continues to document bounded registrar-batch concurrency behavior,
and that behavior remained stable in both DB lanes.

## Implication

The multi-family Postgres pilot strategy is validated further and can move to
another bounded queue-sensitive family without broad fixture migration.
