# 2026-03-28 - Dermatology Patients Derived From Appointments

## Root Cause
- `DermatologistPanelUnified` was still calling the forbidden `GET /api/v1/patients?department=Derma&limit=100` endpoint for the Patients tab.
- `derma` is not an allowed role for the generic patients list API, so the panel showed a noisy 403 path instead of a safe empty state.

## Fix
- Removed the direct patients list fetch from the dermatology panel.
- Derived the `Patients` tab from already loaded appointment/queue rows, matching the dentist panel pattern.
- Reused local appointment data for edit/view flows so patient interactions no longer depend on the restricted generic patients API.

## Verification
- `npx eslint src/pages/DermatologistPanelUnified.jsx`
- `npm run build`
- Browser proof on `http://127.0.0.1:5173/dermatologist?tab=patients`
- Screenshot: `output/playwright/dermatology-patients-safe.png`

## Notes
- The current clinical dataset has no dermatology appointments, so the Patients tab intentionally renders the empty state with `0` patients.
- The important fix is that the tab is now empty-safe and no longer emits the forbidden patients-list request.
