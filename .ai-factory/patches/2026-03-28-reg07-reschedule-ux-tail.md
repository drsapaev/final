# 2026-03-28 - REG-07 reschedule UX tail

## Root cause
- The registrar table in "All departments" aggregated rows by patient but did not preserve `visit_id` / `appointment_id` metadata through the view model.
- Reschedule actions therefore targeted the row `id`, which was enough for one backend path but left the aggregated visual row feeling stale in the live table.

## Fix
- Preserved `visit_id`, `appointment_id`, `queue_entry_id`, and the corresponding identifier arrays in the registrar view-model:
  - `frontend/src/pages/RegistrarPanel.jsx`
- Updated the reschedule resolution helper to prefer real visit identifiers when available.
- Updated the post-reschedule view cleanup to remove rows by all related identifiers so the table shrinks immediately.

## Verification
- `npm run build` in `C:\final\frontend` passed.
- Live browser smoke on `http://127.0.0.1:5173/registrar-panel?tab=appointments` showed the old `QA Smoke BCDEFG` row collapse to the remaining `Повторный` entry after `🌅 Завтра`.
- Backend `GET /api/v1/registrar/queues/today?target_date=2026-03-28` returned only the remaining `visit_id=751` entry after the reschedule.
- Evidence:
  - `output/playwright/reg-07-reschedule-ux-fixed.png`
  - `output/playwright/reg-07-reschedule-ux-fixed.json`
