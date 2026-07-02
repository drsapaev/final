# 2026-03-28 dentist patients fallback

## Summary
- Dentist panel `Patients` now falls back to queue/appointments-derived cards instead of calling the forbidden role-scoped `GET /patients?department=Dental` endpoint.

## Root cause
- The dentist page still had a direct patients fetch that depended on an endpoint returning `403` for the dentist role on this stack.
- The panel already had the appointment/queue data needed to render patients, so the direct call was unnecessary and created noisy failures.

## Fix
- Reworked `loadPatients` in `DentistPanelUnified.jsx` to prefer `buildDentistPatientsFromAppointments(...)` from already loaded appointment rows.
- If no appointments are available yet, the panel now asks the dentist appointments loader to populate the data from the canonical queue/appointments path.

## Verification
- Fresh browser reload on `/dentist` no longer emitted `GET /api/v1/patients?department=Dental -> 403`.
- The dentist page rendered the empty-safe state cleanly on the current stack.
- Browser evidence captured in `output/playwright/dentist-patients-fallback-clean.png`.
