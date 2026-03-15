# W2D API Reference PWA Visits Verification

## Summary

This was a bounded docs-vs-code verification pass for `docs/API_REFERENCE.md`.

The goal was not to fully re-document every patient and visit workflow. The
goal was to correct high-confidence drift in the `Patient Appointments (PWA)`
and `Visits` sections while keeping the slice docs-only.

## Findings

### Patient portal routes were still documented under the wrong prefix

- the doc still advertised:
  - `GET /patient/appointments`
  - `GET /patient/appointments/{id}`
  - `POST /patient/appointments/{id}/cancel`
  - `POST /patient/appointments/{id}/reschedule`
  - `GET /patient/appointments/{id}/available-slots`
  - `GET /patient/results`
- the current published patient-facing OpenAPI instead exposes:
  - `GET /api/v1/patients/appointments`
  - `GET /api/v1/patients/appointments/{appointment_id}`
  - `GET /api/v1/patients/results`
- `api.py` mounts `patients.router` at `/patients`; there is no mounted
  `patient_appointments.py` owner

### Current patient portal appointment surface is smaller than the old docs implied

- the currently published patient self-service contract is read-only for
  appointments and lab results
- the old cancel/reschedule flow is not published in the current OpenAPI
- the nearest published `available-slots` route now lives at
  `/api/v1/schedule/available-slots`, which is a staff-facing schedule helper,
  not a patient portal action

### Visits section was still framed as plain `/visits/` CRUD

- the doc still advertised:
  - `GET /visits/`
  - `POST /visits/`
  - `PUT /visits/{id}`
  - `DELETE /visits/{id}`
- the current published OpenAPI instead exposes:
  - `GET /api/v1/visits/visits`
  - `POST /api/v1/visits/visits`
  - `GET /api/v1/visits/visits/{visit_id}`
  - `POST /api/v1/visits/visits/{visit_id}/services`
  - `POST /api/v1/visits/visits/{visit_id}/status`
  - `POST /api/v1/visits/visits/{visit_id}/reschedule`
  - `POST /api/v1/visits/visits/{visit_id}/reschedule/tomorrow`
  - `GET /api/v1/visits/info/{token}`

### Visits request and access notes had drift

- the old create example used `service_ids` and `scheduled_at`, but the current
  published create model is centered on `patient_id`, `doctor_id`, `notes`,
  `planned_date`, and optional `source`
- read routes `GET /visits/visits` and `GET /visits/visits/{visit_id}` are
  currently published without a `security` block
- mutation routes remain authenticated in the current OpenAPI

## What changed

- updated the `Patient Appointments (PWA)` section in `docs/API_REFERENCE.md`
  to the current `/patients/*` self-service surface
- removed stale patient-facing cancel/reschedule/available-slots claims
- updated the `Visits` section in `docs/API_REFERENCE.md` to the live
  `/visits/visits*` shape
- removed stale visits update/delete claims
- downgraded access and request-shape claims where the current published
  contract is looser or structurally different than the old docs implied

## Evidence used

- `backend/openapi.json`
- `backend/app/api/v1/api.py`
- `backend/app/api/v1/endpoints/patients.py`
- `backend/app/api/v1/endpoints/visits.py`
- `backend/app/api/v1/endpoints/schedule.py`

## Recommended next step

Continue the broader `API_REFERENCE.md` verification track with another bounded
slice rather than a full rewrite.

Good next candidates:

- `Patients`
- `Schedule`
