# Admin Panel Deep Audit: Browser QA

Date: 2026-06-01

Mode: audit-only. No runtime code changed.

## Environment

- Backend: `http://localhost:18000`
- Frontend: `http://localhost:5173`
- Database: `clinic_dev`
- Auth: short-lived dev admin token, stored in `%TEMP%` during QA only
- Browser automation: Playwright via frontend dev dependencies

## Viewports

- `375x812`
- `768x1024`
- `1280x800`
- `1920x1080`

## Route Set

35 admin routes were checked across all four viewports: 140 route/viewport combinations.

Included:

- Overview routes: `/admin`, `/admin/analytics`, `/admin/webhooks`, `/admin/reports`, `/admin/system`, `/admin/cloud-printing`, `/admin/medical-equipment`, `/admin/graphql-explorer`
- Management routes: `/admin/users`, `/admin/doctors`, `/admin/services`, `/admin/queue-cabinet-management`, `/admin/patients`, `/admin/appointments`, `/admin/all-free`
- System/contextual routes: `/admin/benefit-settings`, `/admin/wizard-settings`, `/admin/payment-providers`, `/admin/clinic-management`, `/admin/clinic-settings`, `/admin/queue-settings`, `/admin/ai-settings`, `/admin/telegram-settings`, `/admin/display-settings`, `/admin/integrations/telegram`, `/admin/notifications`, `/admin/phone-verification`, `/admin/activation`, `/admin/finance`, `/admin/settings`, `/admin/security`, `/admin/audit`, `/admin/advanced-users`, `/admin/file-management`, `/admin/user-select`

## Summary

| Check | Result |
| --- | --- |
| Route/viewport combinations | 140 |
| Navigation errors | 0 |
| Login redirects | 0 |
| Forbidden pages | 0 |
| Not-found pages | 0 |
| Unknown-section pages | 0 |
| Horizontal overflow | 0 |
| Unnamed buttons | 0 |
| Routes with critical failed requests | 3 route families |
| Route/viewport rows with failed requests | 12 |
| Route/viewport rows with console errors/warnings | 16 |

Raw local artifact:

- `%TEMP%\admin-panel-deep-qa-2026-06-01.json`

This artifact is intentionally not committed.

## Failed Request Matrix

| Route | Viewports affected | Failed requests | Severity |
| --- | ---: | --- | --- |
| `/admin/services` | 4/4 | `500 /api/v1/services` | P0 |
| `/admin/reports` | 4/4 | `500 /api/v1/reports/daily-summary` | P1 |
| `/admin/file-management` | 4/4 | `422 /api/v1/files/stats`, `401 /api/v1/files/` after browser redirect | P0 |

## Console / Runtime Warnings

| Route | Evidence | Severity |
| --- | --- | --- |
| `/admin/services` | Backend `GET /services` 500, `MacOSTable` column title PropTypes warning, invalid table nesting warning | P0/P2 |
| `/admin/reports` | Daily summary API 500 and quick-report load error | P1 |
| `/admin/file-management` | Files stats 422 and file-list 401 in browser flow | P0 |
| `/admin/graphql-explorer` | React warning: `textareaStyle` prop reaches DOM textarea | P2 |

## Direct API Follow-Up Checks

After browser QA, direct backend calls with the same admin token showed:

- `GET http://localhost:18000/api/v1/files/` returned `200`.
- Browser route still saw `401 http://localhost:18000/api/v1/files/` after `/api/v1/files` redirected to `/api/v1/files/`.

Interpretation:

- File list failure is likely a frontend endpoint/proxy/redirect/auth issue, not an admin RBAC denial.
- File stats failure is endpoint mismatch: frontend uses `/files/stats`, backend file-system route has `/statistics` and dynamic `/{file_id}` catches `stats`.

## Blocked / Not Covered

- Create/edit/delete/export/test actions were not clicked because this was audit-only and no data mutation was allowed.
- Keyboard traversal was sampled by checking focusable controls and unnamed buttons, not by performing full manual tab-order review per route.
- Screenshots were not committed; QA results are summarized in docs and the temp JSON artifact.
