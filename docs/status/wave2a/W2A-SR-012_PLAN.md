# W2A-SR-012 Plan

Date: 2026-05-04
Replacement for: PR #58

## Scope

- `GET /api/v1/visits/visits` -> `list_visits`
- `GET /api/v1/visits/visits/{visit_id}` -> `get_visit`

## Target

- Router delegates read-only visit access to `VisitsApiService`.
- Service/repository remain the DB boundary.
- Route paths and response models stay unchanged.

## Explicit Non-Scope

- `create_visit`
- `add_service`
- `set_status`
- `reschedule_visit`
- `reschedule_visit_tomorrow`
- Queue, payment, EMR, migration, workflow, and frontend files
