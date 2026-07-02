# 2026-03-28 - REG-04 repeat-create and admin guards

## Context
- Repeat-appointment smoke in the registrar/admin appointments flow hit two issues:
  - `AppointmentWizardV2` assumed every `services` entry was a string and crashed on object-shaped repeat data.
  - `AdminPanel` appointments rendering assumed `patientName` / `doctorName` were always present and crashed on `split(...)` for sparse rows.

## Fix
- Normalized repeat-service inputs in `AppointmentWizardV2` before `toUpperCase()` / `toLowerCase()` comparisons.
- Added defensive appointment display helpers in `AdminPanel` for patient/doctor name and specialization fallbacks.
- Kept the appointments table and delete confirmation resilient when backend data is partially shaped.

## Verification
- Live browser smoke created a repeat appointment for an existing patient on the admin appointments screen.
- Appointments table count moved from `6` to `7`.
- Saved evidence: `C:/final/output/playwright/reg-04-repeat-smoke-final.png`
- Frontend validation:
  - `npx eslint C:/final/frontend/src/components/wizard/AppointmentWizardV2.jsx C:/final/frontend/src/pages/AdminPanel.jsx`
  - `npm run build`
