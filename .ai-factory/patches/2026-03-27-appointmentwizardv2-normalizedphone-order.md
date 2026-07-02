# AppointmentWizardV2 normalizedPhone initialization order

Date: 2026-03-27

## Problem
- `AppointmentWizardV2.handleComplete()` referenced `normalizedPhone` and `normalizedPhoneDigits` in the edit-mode branches before the `const` declarations were reached.
- When the registrar wizard flowed through the lab-service path, this surfaced as `Cannot access 'normalizedPhone' before initialization` and blocked completion.

## Fix
- Moved the `normalizedPhone` / `normalizedPhoneDigits` derivation to the top of `handleComplete`, immediately after `patientId` is initialized.
- Removed the later duplicate declaration so all downstream branches reuse the same normalized values.

## Verification
- Targeted eslint on `frontend/src/components/wizard/AppointmentWizardV2.jsx` passed.
- Live smoke on `/registrar-panel` now completes the new appointment flow and returns `200` from:
  - `POST /api/v1/patients/`
  - `POST /api/v1/registrar/cart`
- Browser proof shows a live registrar row for `QA Smoke BCDEFG`, invoice `319`, and the lab queue confirms visit `748` in `/lab-panel`.
