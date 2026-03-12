# W2D registrar_integration_api_service cleanup plan

Date: 2026-03-11
Mode: bounded cleanup

## Scope

- `backend/app/services/registrar_integration_api_service.py`
- stale service-boundary gate alignment
- validation:
  - `pytest tests/unit/test_service_repository_boundary.py -q`
  - `pytest tests/test_openapi_contract.py -q`
  - `pytest -q`

## Why this candidate is in scope

The mounted registrar integration runtime already goes through:

- `backend/app/api/v1/endpoints/registrar_integration.py`
- `backend/app/services/batch_patient_service.py`
- `backend/app/services/queue_domain_service.py`

`registrar_integration_api_service.py` is a duplicate service-router mirror
rather than the mounted runtime owner.

## Evidence

- no confirmed source imports in `backend/app`, `backend/tests`, or
  `frontend/src`
- `backend/app/api/v1/api.py` includes `registrar_integration.router` from the
  endpoint module, not this service-side mirror
- prior Wave 2C docs already classified the file as `DEAD_OR_DUPLICATE`

## Out of scope

- mounted registrar integration behavior
- `queue_batch_service.py`
- batch allocator semantics
- broader registrar refactor
