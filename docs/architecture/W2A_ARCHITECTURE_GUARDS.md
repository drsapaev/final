# Wave 2A Architecture Guards

Date: 2026-03-06  
Scope: post-slice guardrails for completed non-protected W2A slices.

## Guard Added

### Guard ID: `W2A-G-001` (Messaging Router Boundary)

- Type: lightweight architecture test
- File: `backend/tests/architecture/test_w2a_router_boundaries.py`
- Intent:
  - ensure messages router module uses service-first wiring
  - prevent direct ORM/session calls from reappearing in router layer

Assertions:
1. `backend/app/api/v1/endpoints/messages.py` must import router from `app.services.messages_api_service`.
2. `backend/app/api/v1/endpoints/messages.py` must not contain direct DB calls such as:
   - `db.query(...)`
   - `db.add(...)`
   - `db.commit(...)`
   - `db.refresh(...)`
   - `db.rollback(...)`
   - `db.execute(...)`
   - `db.delete(...)`
   - `db.flush(...)`

Why this guard:
- low-noise and deterministic
- focused on completed slice boundary only
- prevents regression to router-level ORM anti-pattern

### Guard ID: `W2A-G-002` (Services Catalog Router Boundary)

- Type: lightweight architecture test
- File: `backend/tests/architecture/test_w2a_router_boundaries.py`
- Intent:
  - ensure non-protected catalog handlers in `services.py` delegate to `ServicesApiService`
  - prevent direct router-level `db.*` calls from returning inside executed catalog handlers

Covered handlers:
- `list_service_categories`
- `create_service_category`
- `update_service_category`
- `delete_service_category`
- `list_services`
- `get_service`
- `create_service`
- `update_service`
- `delete_service`
- `list_doctors_temp`

Assertions:
1. Each covered handler contains `ServicesApiService(db)`.
2. Covered handler blocks do not contain direct DB session calls (`db.query`, `db.commit`, `db.refresh`, `db.delete`, `db.execute`, etc.).

Why this guard:
- protects only the completed catalog sub-slice
- avoids false positives on queue-adjacent handlers intentionally left untouched
- keeps CI signal stable and narrow

### Guard ID: `W2A-G-003` (Visits Read-Only Router Boundary)

- Type: lightweight architecture test
- File: `backend/tests/architecture/test_w2a_router_boundaries.py`
- Intent:
  - ensure read-only visit handlers in `visits.py` delegate to `VisitsApiService`
  - prevent direct router-level `db.*` calls from reappearing in the completed read-only sub-slice

Covered handlers:
- `list_visits`
- `get_visit`

Assertions:
1. Each covered handler contains `VisitsApiService(db)`.
2. Covered handler blocks do not contain direct DB session calls (`db.query`, `db.commit`, `db.refresh`, `db.delete`, `db.execute`, etc.).

Why this guard:
- protects only the completed read-only visits sub-slice
- avoids false positives on remaining write handlers in the same mixed module
- keeps the guard deterministic while Wave 2A is still proceeding slice-by-slice

### Guard ID: `W2A-G-004` (Visits Safe Write Router Boundary)

- Type: lightweight architecture test
- File: `backend/tests/architecture/test_w2a_router_boundaries.py`
- Intent:
  - ensure non-queue visit write handlers delegate to `VisitsApiService`
  - prevent direct router-level session writes from reappearing in the completed safe-write sub-slice

Covered handlers:
- `create_visit`
- `add_service`

Assertions:
1. Each covered handler contains `VisitsApiService(db)`.
2. Covered handler blocks do not contain direct DB session calls (`db.query`, `db.commit`, `db.refresh`, `db.delete`, `db.execute`, etc.).

Why this guard:
- protects only the completed safe-write visit handlers
- avoids false positives on remaining queue-coupled handlers in the same module
- keeps CI focused on slices that are actually complete

## Existing Complementary Guard

- `backend/tests/unit/test_service_repository_boundary.py`
- already enforces "service logic block avoids direct ORM calls" for many `*_api_service.py` modules
- new W2A guard complements it by covering API router boundary (not only service logic block)

## CI/Runtime Impact

- No workflow changes required.
- Guard executes inside existing `pytest -q` run.
- No flaky external dependency or network dependency.

## Expansion Plan

- If additional non-protected slices are completed, add similarly narrow module-specific guards.
- Do not introduce global regex guard over all routers until protected-zone slices are human-reviewed.
