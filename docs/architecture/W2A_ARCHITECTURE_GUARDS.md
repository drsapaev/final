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

