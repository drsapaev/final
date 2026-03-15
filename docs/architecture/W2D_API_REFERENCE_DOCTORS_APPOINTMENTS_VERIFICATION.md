# W2D API Reference Doctors Appointments Verification

## Summary

This was a bounded docs-vs-code verification pass for `docs/API_REFERENCE.md`.

The goal was not to fully re-document every doctor-facing and
appointment-adjacent workflow. The goal was to correct high-confidence drift in
the `Doctors` section and add an honest curated `Appointments` section for the
currently published operational `/appointments*` surface.

## Findings

### Doctors section was still advertising a route family that no longer exists

- the doc still advertised:
  - `GET /doctors/`
  - `GET /doctors/{id}/schedule`
  - `GET /doctors/{id}/queue`
- there is no published `/api/v1/doctors*` family in the current OpenAPI
- the current published doctor-related surface is split across:
  - `/api/v1/doctor-info/*`
  - `/api/v1/doctor/*`
  - `/api/v1/admin/doctors*`
  - appointment-linked helpers such as
    `/api/v1/appointments/doctor/{doctor_id}/schedule`

### Doctor lookup and doctor workflow routes are now separate concerns

- `doctor_info.py` owns the lookup-style doctor and department reads
- `/doctor/*` publishes doctor self-service, queue, calendar, and visit helper
  routes
- `/admin/doctors*` publishes admin doctor-management routes
- the old docs collapsed those surfaces into one obsolete `/doctors/*` summary

### API reference was missing a general appointments section for the live operational surface

- current published OpenAPI exposes a broad authenticated
  `/api/v1/appointments*` family including:
  - CRUD under `/api/v1/appointments/` and
    `/api/v1/appointments/{appointment_id}`
  - doctor and department schedule lookups
  - visit lifecycle routes
  - EMR and prescription subresources
  - payment-adjacent helper routes
  - operational day-control routes
- the file only had the separate `Patient Appointments (PWA)` section, which is
  not the same contract

### Appointment surface also contains path-shape and access nuances the old docs did not surface

- `POST /api/v1/appointments` is a distinct report-generation route and not the
  same operation as `POST /api/v1/appointments/`
- `GET /api/v1/appointments/stats` and `GET /api/v1/appointments/qrcode` are
  still published but explicitly deprecated
- `POST /api/v1/appointments/{appointment_id}/mark-paid` is currently published
  without a `security` block while the other reviewed appointment routes remain
  authenticated

## What changed

- replaced the stale `Doctors` section in `docs/API_REFERENCE.md` with a
  curated split-surface map
- documented `/doctor-info/*`, `/doctor/*`, `/admin/doctors*`, and the
  appointment-linked doctor schedule helper
- added a new curated `Appointments` section covering the live operational
  `/appointments*` family
- called out the distinct bare `POST /appointments` report-generation route
- marked the deprecated `/appointments/stats` and `/appointments/qrcode`
  surfaces conservatively instead of removing them from the reference
- downgraded the `mark-paid` access note to match the current published OpenAPI

## Evidence used

- `backend/openapi.json`
- `backend/app/api/v1/api.py`
- `backend/app/api/v1/endpoints/doctor_info.py`
- `backend/app/api/v1/endpoints/appointments.py`

## Recommended next step

Continue the broader `API_REFERENCE.md` verification track with another bounded
slice rather than a full rewrite.

Good next candidates:

- `Patient Appointments (PWA)`
- `Visits`
