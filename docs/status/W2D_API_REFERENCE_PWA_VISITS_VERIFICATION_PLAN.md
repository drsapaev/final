# W2D API Reference PWA Visits Verification Plan

Scope:

- verify the `Patient Appointments (PWA)` and `Visits` sections in
  `docs/API_REFERENCE.md` against current OpenAPI and mounted owners
- keep the slice docs-only
- avoid turning the pass into a full patient-portal or visit-lifecycle
  specification rewrite

Evidence targets:

- `backend/openapi.json`
- `backend/app/api/v1/api.py`
- `backend/app/api/v1/endpoints/patients.py`
- `backend/app/api/v1/endpoints/visits.py`
- `backend/app/api/v1/endpoints/schedule.py`

Expected outcome:

- stale `/patient/appointments*` claims removed or downgraded
- current `/patients/*` self-service appointment/results surface reflected
- stale `/visits/` CRUD claims removed
- current `/visits/visits*` route family reflected
- request and access notes downgraded where the published contract differs
