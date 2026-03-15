# W2D API Reference PWA Visits Verification Status

Status: completed

What changed:

- the `Patient Appointments (PWA)` section in `docs/API_REFERENCE.md` now
  reflects the live `/patients/appointments*` and `/patients/results` surface
- stale patient-facing `cancel`, `reschedule`, and `available-slots` claims
  were removed
- the `Visits` section now reflects the live `/visits/visits*` route family
- stale visits update/delete claims were removed
- access and request-shape notes were downgraded where the current published
  contract differs from the older docs

Validation:

- `pytest tests/test_openapi_contract.py -q` -> `14 passed`
- route and schema claims were checked against:
  - `backend/openapi.json`
  - `backend/app/api/v1/api.py`
  - `backend/app/api/v1/endpoints/patients.py`
  - `backend/app/api/v1/endpoints/visits.py`
  - `backend/app/api/v1/endpoints/schedule.py`

Result:

- the touched docs no longer advertise a non-existent `/patient/appointments*`
  surface
- the touched docs no longer describe visits as the old plain `/visits/` CRUD
- the reviewed sections better match the published contract while remaining a
  curated high-level reference
