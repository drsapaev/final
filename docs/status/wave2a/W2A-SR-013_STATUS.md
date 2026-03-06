# W2A-SR-013 Status

Status: `done`  
Date: 2026-03-06  
Execution contract: `.ai-factory/contracts/w2a-sr-013.contract.json`

## Scope

- Module: `backend/app/api/v1/endpoints/visits.py`
- Executed handlers only:
  - `POST /api/v1/visits/visits`
  - `POST /api/v1/visits/visits/{visit_id}/services`

## Explicit Non-Scope

- Remaining handlers in `visits.py` were left untouched:
  - `POST /api/v1/visits/visits/{visit_id}/status`
  - `POST /api/v1/visits/visits/{visit_id}/reschedule`
  - `POST /api/v1/visits/visits/{visit_id}/reschedule/tomorrow`

## Applied Refactor Shape

- Router handlers now delegate to `VisitsApiService`.
- DB/audit/transaction logic for the executed handlers now flows through:
  - `router -> VisitsApiService -> VisitsApiRepository`
- Route paths, status codes, and response models stayed unchanged.

## Files Changed

- `backend/app/api/v1/endpoints/visits.py`
- `backend/app/services/visits_api_service.py`
- `backend/tests/unit/test_visits_router_service_wiring.py`
- `backend/tests/architecture/test_w2a_router_boundaries.py`

## Architecture Change

- Removed router-level insert, audit, normalization, and commit logic from `create_visit` and `add_service`.
- Preserved the previous `create_visit` CRUD-path `source` fallback by aligning `VisitsApiService.create_visit` with the old router behavior.
- Added a narrow architecture guard that covers only the completed safe-write handlers and intentionally ignores the remaining queue-coupled handlers.

## Protected Zone Check

- No payment/auth/EMR/alembic/secrets/workflow files were modified.
- Queue-coupled visit handlers (`set_status`, `reschedule_*`) were not changed.

## Tests Run

- `cd backend && pytest -q`
- `cd backend && pytest tests/test_openapi_contract.py -q`
- `cd backend && pytest tests/unit -q`

## Results

- `pytest -q` -> `658 passed, 3 skipped`
- `pytest tests/test_openapi_contract.py -q` -> `10 passed`
- `pytest tests/unit -q` -> `383 passed`

## Regressions

- No regressions detected.
- OpenAPI contract stayed green.
