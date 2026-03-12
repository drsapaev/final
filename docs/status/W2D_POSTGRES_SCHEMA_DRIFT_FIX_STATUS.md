## Wave 2D Postgres Schema Drift Fix Status

Date: 2026-03-10  
Status: `SUCCESS`

## Fixed blocker

Resolved the Postgres-invalid foreign key mismatch:

- `doctor_treatment_templates.doctor_id`
- `users.id`

The corrected ownership is `doctor_treatment_templates.doctor_id -> users.id`,
with `doctor_id` now stored as `Integer`.

## Validation

### Narrow schema guard

- `pytest tests/unit/test_doctor_treatment_template_schema.py -q`
- Result: `1 passed`

### SQLite pilot baseline

- `pytest tests/characterization/test_queue_allocator_characterization.py tests/characterization/test_queue_allocator_concurrency.py -q -c pytest.ini`
- Result: `7 passed`

### Postgres pilot

- `pytest tests/characterization/test_queue_allocator_characterization.py tests/characterization/test_queue_allocator_concurrency.py -q -c pytest.ini --db-backend=postgres`
- Result: schema bootstrap passed; pilot advanced to runtime assertions and surfaced new follow-on drift

### OpenAPI

- `pytest tests/test_openapi_contract.py -q`
- Result: `10 passed`

### Full backend confidence run

- `pytest -q`
- Result: `782 passed, 3 skipped`

## Outcome

- The original Postgres schema-bootstrap blocker is gone.
- The dual validation pilot strategy remains validated.
- The next blockers are distinct follow-on issues, not regressions of this fix.
