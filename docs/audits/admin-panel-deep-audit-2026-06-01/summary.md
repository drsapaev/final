# Admin Panel Deep Audit Summary

Date: 2026-06-01

Mode: audit-only. No runtime code changed.

## Verdict

AdminPanel is route-complete enough to render the full admin map, but not functionally clean yet.

The good news:

- No audited route redirected to login, forbidden, not-found, or unknown-section.
- No horizontal overflow across the four required viewports.
- No unnamed icon-only buttons were found in the audited route shells.

The important problems:

- Core admin service catalog is blocked by `GET /api/v1/services` 500.
- File management is broken in browser flow due endpoint mismatch and redirect/auth behavior.
- Reports daily summary is broken because reporting expects `Visit.total_amount`.
- Several admin domains have duplicate/split owners, creating wrong-fix risk for future agents.

## P0 Backlog

1. Fix `/admin/services` service list.
   - Evidence: `/api/v1/services` returns 500 in all four viewports.
   - Likely root: `ServiceOut` serializer/schema mismatch around `specialist`.
   - Slice: backend serialization fix + targeted service list test + browser smoke.

2. Fix `/admin/file-management` file APIs in browser flow.
   - Evidence: `/api/v1/files/stats` returns 422; `/api/v1/files` redirects to backend `/api/v1/files/` and browser flow receives 401.
   - Likely root: frontend endpoint mismatch (`stats` vs backend `statistics`) plus redirect/auth loss.
   - Slice: align endpoint naming and use canonical API client/origin helper.

## P1 Backlog

1. Fix `/admin/reports` daily summary.
   - Evidence: `/api/v1/reports/daily-summary` returns 500.
   - Backend log: `Visit object has no attribute total_amount`.
   - Slice: calculate totals from current payment/visit-service source of truth.

2. Decide canonical owners for duplicate admin surfaces.
   - Analytics: `AnalyticsPage` vs `AnalyticsDashboard`.
   - Settings: `Settings` vs `UnifiedSettings`.
   - Telegram: `TelegramManager` vs `UnifiedTelegramManagement`.
   - Notifications: `EmailSMSManager` vs `UnifiedNotifications`.
   - Users: `UnifiedUserManagement` vs `UserManagement`.

## P2 Backlog

1. Remove misleading dashboard/analytics quick switcher from webhooks or make it integration-aware.
2. Give contextual settings routes a parent/breadcrumb/active section.
3. Fix GraphQL Explorer `textareaStyle` DOM prop warning.
4. Fix ServiceCatalog table PropTypes and table-nesting warnings after service data loads.
5. Consolidate repeated local `AdminTabs` implementations into one design-system primitive.

## P3 Backlog

1. Rebalance sidebar grouping after P0/P1 fixes.
2. Move webhooks/GraphQL toward integrations.
3. Move cloud printing / medical equipment toward operations/devices.
4. Tighten naming for hidden/contextual settings routes.

## Recommended Fix Slices

1. `fix(admin-services): restore service catalog list`
   - Scope: backend `/services` serialization and targeted frontend smoke.

2. `fix(admin-files): align file manager endpoints`
   - Scope: file-management endpoint names/auth behavior only.

3. `fix(admin-reports): restore daily summary totals`
   - Scope: reporting service totals only.

4. `docs(admin): define canonical admin route owners`
   - Scope: route owner table, no runtime changes.

5. `refactor(admin): consolidate one duplicated admin surface`
   - Pick only one family: Telegram, notifications, settings, analytics, or users.

6. `fix(admin-ui): normalize admin tab primitive`
   - Scope: shared tab primitive after owner decisions.

## Validation Evidence

- `.\scripts\check_dev_clinic.ps1`: PASS before browser QA.
- Playwright browser QA: 35 routes x 4 viewports = 140 checks.
- `clinic_dev` was used.
- No DB reset/seed was run.
- No runtime files were changed.

## Remaining Unknowns

- Full create/edit/delete/export/test action behavior was not exercised because this audit PR is read-only.
- Route ownership cleanup may require product decisions before code changes.
- API failures should be fixed in targeted PRs with backend tests, not hidden behind frontend fallbacks.

## Stop Conditions

- Do not fix findings inside this audit PR.
- Do not delete aliases until route-registry compatibility is reviewed.
- Do not merge UI route owners with DB/security/payment/notification ownership changes in the same PR.
