# Patient Appointments Endpoint Cleanup Plan

Scope:
- delete dead endpoint artifact `backend/app/api/v1/endpoints/patient_appointments.py`
- correct stale TODO review content that still referenced the dead file

Evidence:
- `backend/app/api/v1/api.py` does not mount `patient_appointments.router`
- `backend/openapi.json` contains the mounted patient appointments surface under
  `patients.py`, not under `/patient/*`
- no confirmed frontend or backend runtime import of the endpoint module remains
- `docs/TODO_REVIEW.md` still described TODOs inside the dead endpoint file

Why this is safe:
- the endpoint was not mounted, so deleting it cannot change runtime routing
- the mounted patient appointments surface already has a different live owner

Out of scope:
- cleanup of `patient_appointments_api_service.py`
- patient portal behavior changes
- redesign of mounted patient appointment APIs
