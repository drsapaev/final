# W2A-SR-012 Plan

Date: 2026-03-06  
Execution contract: `.ai-factory/contracts/w2a-sr-012.contract.json`

## Files

- `backend/app/api/v1/endpoints/visits.py`
- `backend/app/services/visits_api_service.py`
- `backend/app/repositories/visits_api_repository.py`
- `backend/tests/unit/test_visits_router_service_wiring.py`
- `backend/tests/architecture/test_w2a_router_boundaries.py`

## Endpoints / Functions

- `GET /api/v1/visits/visits` -> `list_visits`
- `GET /api/v1/visits/visits/{visit_id}` -> `get_visit`

## Current Anti-Pattern

- Router-level read-only handlers in `visits.py` still build reflected tables, compose SQL, and execute session queries directly.
- The same module also contains write handlers with queue-coupled semantics, so only the read-only path is safe in this slice.

## Target Architecture

- Router validates input and delegates to `VisitsApiService`.
- `VisitsApiService` orchestrates read-only visit lookup/list behavior.
- `VisitsApiRepository` remains the boundary for DB execution.

## Expected Service / Repository Wiring

- `list_visits`: `router -> VisitsApiService.list_visits(...) -> VisitsApiRepository.execute(...)`
- `get_visit`: `router -> VisitsApiService.get_visit(...) -> VisitsApiRepository.execute(...)`

## Risk Level

- Low to medium.
- Low because service/repository implementations already exist for both handlers.
- Medium because `visits.py` is a mixed module with protected write handlers that must stay untouched.

## Protected Zone Check

- Selected handlers are read-only and do not update queue/payment/auth state.
- `set_status`, `reschedule_visit`, and `reschedule_visit_tomorrow` remain explicitly out of scope.
- No protected-zone files outside `visits.py` are in scope.
