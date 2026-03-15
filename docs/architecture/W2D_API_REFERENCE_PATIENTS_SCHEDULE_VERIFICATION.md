# W2D API Reference Patients Schedule Verification

## Summary

This was a bounded docs-vs-code verification pass for `docs/API_REFERENCE.md`.

The goal was not to fully re-document every patient-registry and scheduling
workflow. The goal was to correct high-confidence drift in the `Patients`
section and add a missing curated `Schedule` section while keeping the slice
docs-only.

## Findings

### Patients section was still an underspecified early summary

- the doc still advertised only:
  - `GET /patients/`
  - `GET /patients/{id}`
  - `POST /patients/`
- the query note still used stale `search` instead of the current `q` plus
  `phone` split
- the current published `/api/v1/patients*` surface is broader and also
  exposes:
  - `PUT /api/v1/patients/{patient_id}`
  - `DELETE /api/v1/patients/{patient_id}`
  - `GET /api/v1/patients/{patient_id}/appointments`
  - family relation helpers
  - primary-contact helper
  - deleted/soft-delete/restore helpers

### Patient portal and patient registry surfaces needed clearer separation

- the current self-service patient portal reads are already published under:
  - `/api/v1/patients/appointments`
  - `/api/v1/patients/appointments/{appointment_id}`
  - `/api/v1/patients/results`
- those routes are not the same surface as the broader registry and family
  management routes under `/api/v1/patients/{patient_id}*`
- the honest docs move was to keep the main `Patients` section focused on the
  registry surface and point to the already-updated `Patient Appointments
  (PWA)` section for self-service reads

### Schedule surface was missing entirely from the API reference

- the current published OpenAPI exposes a live `/api/v1/schedule*` family:
  - `GET/POST /api/v1/schedule`
  - `DELETE /api/v1/schedule/{id}`
  - `GET /api/v1/schedule/weekly`
  - `GET /api/v1/schedule/daily`
  - `GET /api/v1/schedule/available-slots`
  - `GET /api/v1/schedule/doctors`
  - `GET /api/v1/schedule/departments`
- the updated PWA section already needed to mention `/schedule/available-slots`,
  but there was still no section documenting that live owner surface

### Schedule access notes are more specific than OpenAPI alone suggests

- current published OpenAPI shows all reviewed `/schedule*` routes as
  authenticated
- the live owner in `schedule.py` uses:
  - `Admin`, `Registrar`, `Doctor` for lookup/list helpers
  - `Admin` only for create/delete
- the docs can state that split because the mounted owner is straightforward
  and local to one module

## What changed

- updated the `Patients` section in `docs/API_REFERENCE.md` to a curated modern
  `/patients*` map
- replaced stale `search` with the live `q` plus `phone` query split
- added the adjacent patient registry helpers that were missing from the old
  mini-summary
- added a new curated `Schedule` section for the live `/schedule*` route
  family
- documented the lookup-versus-admin role split on schedule routes

## Evidence used

- `backend/openapi.json`
- `backend/app/api/v1/api.py`
- `backend/app/api/v1/endpoints/patients.py`
- `backend/app/api/v1/endpoints/schedule.py`

## Recommended next step

Continue the broader `API_REFERENCE.md` verification track with another bounded
slice rather than a full rewrite.

Good next candidates:

- `Health`
- `Authentication Header`
