# W2A-SR-013 Plan

Date: 2026-03-06  
Execution contract: `.ai-factory/contracts/w2a-sr-013.contract.json`

## Files

- `backend/app/api/v1/endpoints/visits.py`
- `backend/app/services/visits_api_service.py`
- `backend/app/repositories/visits_api_repository.py`
- `backend/tests/unit/test_visits_router_service_wiring.py`
- `backend/tests/architecture/test_w2a_router_boundaries.py`

## Endpoints / Functions

- `POST /api/v1/visits/visits` -> `create_visit`
- `POST /api/v1/visits/visits/{visit_id}/services` -> `add_service`

## Current Anti-Pattern

- Router-level write handlers in `visits.py` still create inserts, normalize service codes, write audit logs, and commit transactions directly.
- The same module also contains queue-coupled write handlers; those remain out of scope.

## Target Architecture

- Router validates input and delegates to `VisitsApiService`.
- `VisitsApiService` orchestrates visit creation and add-service flow while preserving existing audit/transaction behavior.
- `VisitsApiRepository` remains the DB execution boundary.

## Expected Service / Repository Wiring

- `create_visit`: `router -> VisitsApiService.create_visit(...) -> VisitsApiRepository`
- `add_service`: `router -> VisitsApiService.add_service(...) -> VisitsApiRepository`

## Risk Level

- Medium.
- Safe because both service methods already exist and stay inside the same module boundary.
- The main risk is response/audit drift in `create_visit`, so this slice includes a behavior-preserving alignment in the service path.

## Protected Zone Check

- Selected handlers do not update queue state.
- `set_status` and `reschedule_*` remain explicitly out of scope because they are queue-coupled.
- No auth/payment/EMR/alembic/workflow files are in scope.
