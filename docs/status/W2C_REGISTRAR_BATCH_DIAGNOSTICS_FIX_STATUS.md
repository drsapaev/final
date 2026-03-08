# Wave 2C Registrar Batch Diagnostics Fix Status

Date: 2026-03-08
Status: `done`
Mode: behaviour-correction, small diff

## Files Changed

- `backend/app/api/v1/endpoints/registrar_integration.py`
- `backend/tests/characterization/test_registrar_batch_allocator_characterization.py`
- `backend/tests/unit/test_registrar_batch_reuse_existing_entry.py`
- `docs/architecture/W2C_REGISTRAR_BATCH_BEHAVIOR_CORRECTION.md`
- `docs/status/W2C_REGISTRAR_BATCH_BOUNDARY_READINESS.md`
- `docs/status/W2C_REGISTRAR_BATCH_NEXT_STEP_V3.md`

## Old Behavior

- duplicate gate reused only `waiting` / `called`
- existing `diagnostics` row did not block new allocation
- existing `in_service` row would also have been ignored
- ambiguous multi-row active state had no explicit domain error

## Corrected Behavior

- duplicate gate now checks `waiting`, `called`, `in_service`, `diagnostics`
- existing compatible active row is reused
- no new number is allocated when row is reused
- ambiguity returns explicit `409`

## Commands Run

- `cd backend && pytest tests/characterization/test_registrar_batch_allocator_characterization.py -q -c pytest.ini`
- `cd backend && pytest tests/characterization/test_registrar_batch_allocator_concurrency.py -q -c pytest.ini`
- `cd backend && pytest tests/unit/test_registrar_batch_reuse_existing_entry.py -q`
- `cd backend && pytest tests/characterization -q -c pytest.ini`
- `cd backend && pytest tests/test_openapi_contract.py -q`
- `cd backend && pytest -q`

## Results

- registrar batch characterization: `6 passed`
- registrar batch concurrency characterization: `2 passed`
- registrar batch unit tests: `5 passed`
- full characterization suite: `23 passed`
- OpenAPI contract: `10 passed`
- full backend suite: `718 passed, 3 skipped`

## Stop Conditions Check

No stop condition was hit:

- numbering semantics unchanged
- fairness ordering unchanged
- no payment/billing behavior touched
- scope remained inside mounted registrar batch-only path

## Outcome

Registrar batch-only family is now aligned with its clarified active-entry and
specialist-level claim contract.
