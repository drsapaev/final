## Wave 2D Queues Stats Postgres Pilot Status

Date: 2026-03-10
Mode: pilot-extension, evidence-based

Status: `COMPLETED`

## Scope

Target family:

- `backend/tests/characterization/test_queues_stats_parity_harness.py`

## Outcome

- SQLite lane succeeded
- Postgres lane succeeded
- no additional harness or fixture changes were required

## Results

- SQLite lane:
  `pytest tests/characterization/test_queues_stats_parity_harness.py -q -c pytest.ini`
  -> `3 passed`

- Postgres lane:
  `pytest tests/characterization/test_queues_stats_parity_harness.py -q -c pytest.ini --db-backend=postgres`
  -> `3 passed`

- OpenAPI:
  `pytest tests/test_openapi_contract.py -q`
  -> `10 passed`

## Drift summary

No SQLite-vs-Postgres drift was observed in this family.

The family continues to document:

- strict parity for consumer-visible counters
- compatibility-only mismatch categories

and those expectations remained stable in both lanes.

## Implication

The multi-family Postgres pilot strategy is now validated further and can move
to another queue-sensitive family without broad fixture migration.
