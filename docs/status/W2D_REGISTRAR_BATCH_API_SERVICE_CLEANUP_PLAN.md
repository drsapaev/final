# W2D registrar_batch_api_service cleanup plan

Date: 2026-03-11
Mode: bounded cleanup

## Scope

- `backend/app/services/registrar_batch_api_service.py`
- validation:
  - `pytest tests/test_openapi_contract.py -q`
  - `pytest -q`

## Why this candidate is in scope

The mounted `/registrar/batch` runtime already goes through:

- `backend/app/api/v1/endpoints/registrar_batch.py`
- `backend/app/services/batch_patient_service.py`

`registrar_batch_api_service.py` is a duplicate router-like mirror rather than a
live runtime owner.

## Evidence

- no confirmed source imports in `backend/app` or `backend/tests`
- `backend/app/api/v1/api.py` includes `registrar_batch.router` from the
  endpoint module, not this service-side mirror
- prior Wave 2C docs already classified the file as `DEAD_OR_DUPLICATE`

## Out of scope

- mounted `/registrar/batch` behavior
- `BatchPatientService`
- registrar allocator semantics
- any broader registrar refactor
