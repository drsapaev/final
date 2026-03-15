# W2D API Reference Doctors Appointments Verification Status

Status: completed

What changed:

- the `Doctors` section in `docs/API_REFERENCE.md` now reflects the live split
  between `/doctor-info/*`, `/doctor/*`, `/admin/doctors*`, and the
  appointment-linked doctor schedule helper
- stale `/doctors/*` claims were removed
- a new curated general `Appointments` section now documents the live
  operational `/appointments*` family
- deprecated `/appointments/stats` and `/appointments/qrcode` are now called
  out as compatibility routes
- the access note for `/appointments/{appointment_id}/mark-paid` was
  downgraded to match the current published OpenAPI

Validation:

- `pytest tests/test_openapi_contract.py -q` -> `14 passed`
- route and schema claims were checked against:
  - `backend/openapi.json`
  - `backend/app/api/v1/api.py`
  - `backend/app/api/v1/endpoints/doctor_info.py`
  - `backend/app/api/v1/endpoints/appointments.py`

Result:

- the touched docs no longer advertise a non-existent `/doctors/*` family
- the file now distinguishes patient-side appointments from the broader
  operational `/appointments*` contract
- the reviewed sections better match the published contract while remaining a
  curated high-level reference
