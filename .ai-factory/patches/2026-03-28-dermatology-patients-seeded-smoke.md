# 2026-03-28 - Dermatology Patients Seeded Smoke

## Root Cause
- `DermatologistPanelUnified` only loaded the dermatology appointment dataset when the active tab was `appointments`, so a direct deep-link to `?tab=patients` could render an empty Patients view even when valid seeded data already existed.
- The panel already derived its Patients tab from appointment/queue data, so the missing piece was simply triggering that load on the Patients tab itself.

## Fix
- Extended the dermatology tab loader so `Patients` also calls `loadDermatologyAppointments()`.
- Kept the Patients tab derived from queue/appointment rows instead of falling back to the forbidden generic patients endpoint.

## Verification
- `npx eslint src/pages/DermatologistPanelUnified.jsx`
- `npm run build`
- Browser smoke on `http://127.0.0.1:5173/dermatologist?tab=patients`
- Screenshot: `output/playwright/derm-patients-seeded-smoke.png`

## Notes
- The seeded visit for `QA Smoke BCDEFG` now renders as `1` patient on the Patients tab when the browser is pointed at the healthy backend.
- This keeps the dermatology panel aligned with the existing SSOT pattern: render from appointments/queue, not from a restricted generic patients endpoint.
