# W2D registrar_wizard_api_service cleanup plan

Date: 2026-03-11
Mode: bounded cleanup

## Scope

- `backend/app/services/registrar_wizard_api_service.py`
- stale service-boundary gate alignment
- validation:
  - `pytest tests/unit/test_service_repository_boundary.py -q`
  - `pytest tests/test_openapi_contract.py -q`
  - `pytest -q`

## Why this candidate is in scope

The mounted registrar wizard runtime already goes through:

- `backend/app/api/v1/endpoints/registrar_wizard.py`
- `backend/app/services/registrar_wizard_queue_assignment_service.py`
- `backend/app/services/visit_confirmation_service.py`
- `backend/app/services/morning_assignment.py`

`registrar_wizard_api_service.py` is a duplicate service-router mirror rather
than the mounted runtime owner.

## Evidence

- no confirmed source imports in `backend/app`, `backend/tests`, or
  `frontend/src`
- `backend/app/api/v1/api.py` includes `registrar_wizard.router` from the
  endpoint module, not this service-side mirror
- prior Wave 2C docs already classified the file as `DEAD_OR_DUPLICATE`

## Out of scope

- mounted registrar wizard behavior
- queue allocation semantics
- confirmation semantics
- batch or wizard product flows
