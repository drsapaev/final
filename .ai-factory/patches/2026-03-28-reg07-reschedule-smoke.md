## REG-07 Reschedule Smoke

### Root cause
- Legacy registrar reschedule flows still needed a backend-compatible path while the browser runtime was being refreshed.

### Fix
- Added canonical and legacy alias routes for visit reschedule in `backend/app/api/v1/endpoints/visits.py`.
- Added regression coverage for both `/visits/{id}/reschedule` and `/visits/{id}/reschedule/tomorrow` aliases in `backend/tests/integration/test_visits_reschedule_aliases.py`.

### Verification
- Fresh browser session on the registrar panel successfully moved `visit 9` to `2026-03-29`.
- Backend network proof captured `POST /api/v1/visits/visits/9/reschedule/tomorrow => 200`.
- Database verification confirmed `visit_date=2026-03-29`.
- Browser proof saved to `output/playwright/reg-07-reschedule-success.png` and `output/playwright/reg-07-visit-row.txt`.
