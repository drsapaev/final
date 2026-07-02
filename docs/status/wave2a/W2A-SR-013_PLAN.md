# W2A-SR-013 Plan

Date: 2026-05-04
Replacement for: PR #59

## Scope

- `POST /api/v1/visits/visits` -> `create_visit`
- `POST /api/v1/visits/visits/{visit_id}/services` -> `add_service`

## Target

- Router delegates safe visit writes to `VisitsApiService`.
- Service/repository remain the DB, audit, normalization, and commit boundary.
- Route paths, response models, audit behavior, transaction behavior, and source fallback stay unchanged.

## Explicit Non-Scope

- `set_status`
- `reschedule_visit`
- `reschedule_visit_tomorrow`
- Queue, payment, EMR, migration, workflow, lockfile, and frontend files
