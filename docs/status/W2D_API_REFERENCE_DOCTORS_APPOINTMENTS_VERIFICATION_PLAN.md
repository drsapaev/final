# W2D API Reference Doctors Appointments Verification Plan

Scope:

- verify the `Doctors` section and the missing general `Appointments` coverage
  in `docs/API_REFERENCE.md` against current OpenAPI and mounted owners
- keep the slice docs-only
- avoid turning the pass into a full clinical workflow specification rewrite

Evidence targets:

- `backend/openapi.json`
- `backend/app/api/v1/api.py`
- `backend/app/api/v1/endpoints/doctor_info.py`
- `backend/app/api/v1/endpoints/appointments.py`

Expected outcome:

- stale `/doctors/*` claims removed
- current doctor split between lookup, self-service, admin, and
  appointment-linked helpers reflected
- general operational `/appointments*` surface documented as a curated map
- deprecated and access-sensitive appointment tails downgraded conservatively
