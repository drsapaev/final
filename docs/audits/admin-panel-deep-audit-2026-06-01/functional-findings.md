# Admin Panel Deep Audit: Functional Findings

Date: 2026-06-01

Mode: audit-only. No runtime code changed.

## Findings

### P0: `/admin/services` cannot load service catalog data

Evidence:

- Browser QA: `/admin/services` returned `500 http://localhost:5173/api/v1/services` in all four viewports.
- Frontend console: `GET /services` failed with backend validation error mentioning `ServiceOut` and `specialist` expecting a string.
- Adjacent service endpoints loaded: `/services/categories`, `/services/admin/doctors`, `/departments`, and `/queues/profiles?active_only=false`.

Impact:

- Admin service catalog management is blocked even though the route shell renders.
- Service catalog is a core admin function and also affects registrar service selection.

Likely root:

- Backend service-list serialization/schema mismatch for at least one service row, not a pure frontend rendering issue.

Recommended slice:

- Backend-first service list serialization fix with a focused `/api/v1/services` regression test.
- Then run admin service catalog browser smoke.

### P0: `/admin/file-management` file list/stat UX is broken in browser

Evidence:

- Browser QA: `/admin/file-management` hit `422 /api/v1/files/stats` and `401 http://localhost:18000/api/v1/files/`.
- Direct backend call with the same token to `http://localhost:18000/api/v1/files/` returned `200`.
- Backend log: `/api/v1/files/stats` is parsed as dynamic `{file_id}` and fails integer parsing.
- Source: `frontend/src/components/files/FileManager.jsx` calls `/api/v1/files/stats`, while backend file-system route exposes `/statistics`.
- Source: `FileManager.jsx` calls `/api/v1/files` without trailing slash, causing redirect to `/api/v1/files/`; in browser QA the redirected backend-origin request lost auth and returned 401.

Impact:

- Admin file-management route shell loads but core list/stats behavior is not reliable.

Recommended slice:

- Align frontend with backend file endpoints, or add backend-compatible `/stats`.
- Avoid cross-origin auth loss by using the existing API client or canonical runtime API origin helper.

### P1: `/admin/reports` quick daily summary fails

Evidence:

- Browser QA: `/admin/reports` returned `500 /api/v1/reports/daily-summary` in all four viewports.
- Backend log: `Visit object has no attribute total_amount`.
- Other report endpoints, such as `/reports/files` and `/reports/available-reports`, returned 200.

Impact:

- Reports route loads, but quick daily summary is broken.
- Users see an error state for a primary report-card area.

Likely root:

- Reporting service expects `Visit.total_amount`, but current visit/payment model no longer exposes that field directly.

Recommended slice:

- Fix `reporting_service` to calculate visit totals from the current payment/visit-service source of truth.
- Add one regression test for daily summary with current schema.

### P1: Split route owners create wrong-fix risk

Evidence:

- Analytics: `/admin/analytics` uses `AnalyticsPage`, while `AdminPanel` has an `AnalyticsDashboard` branch.
- Settings: `/admin/settings` uses `Settings`, while `AdminPanel` has `UnifiedSettings` branches.
- Telegram: `/admin/integrations/telegram` uses `TelegramManager`, while `/admin/telegram-settings` uses `UnifiedTelegramManagement`.
- Notifications: `/admin/notifications` uses `EmailSMSManager`, while hidden notification branches use `UnifiedNotifications`.
- Users: `/admin/users` uses `UnifiedUserManagement`, while `/admin/advanced-users` uses `UserManagement`.

Impact:

- Future agents can fix the wrong surface.
- Route-specific behavior can silently diverge.

Recommended slice:

- Write a canonical owner table first, then clean one duplicated route family per PR.

### P2: Webhooks screen shows dashboard/analytics route switcher

Evidence:

- `AdminPanel.jsx` renders `AdminRouteSwitcher current="dashboard"` inside `case 'webhooks'`.
- `AdminRouteSwitcher.jsx` only contains dashboard and analytics route cards.

Impact:

- Webhooks users see a quick switcher that marks dashboard active and does not mention webhooks.

Recommended slice:

- Remove the local switcher from webhooks or expand it to relevant integration routes.

### P2: Contextual routes have weak navigation state

Evidence:

- `/admin/benefit-settings`, `/admin/wizard-settings`, `/admin/payment-providers`, `/admin/clinic-settings`, `/admin/queue-settings`, `/admin/telegram-settings`, `/admin/display-settings`, and `/admin/user-select` have no sidebar nav metadata.
- They render, but users do not get a clear active sidebar anchor.

Impact:

- Direct links work, but users may not know where they are in Admin.

Recommended slice:

- Keep them contextual if intentional, but give each a parent section, breadcrumb, or explicit entry point.

### P2: GraphQL Explorer leaks a non-DOM prop

Evidence:

- Browser console on `/admin/graphql-explorer`: React warning for `textareaStyle` passed to a DOM `textarea`.

Impact:

- Not a task blocker, but it is a noisy React warning in an admin developer tool.

Recommended slice:

- Fix `MacOSTextarea` prop filtering or GraphQLExplorer prop usage.

### P2: Service catalog table markup/prop warnings

Evidence:

- Browser console on `/admin/services`: `MacOSTable` gets an object `columns[0].title` where PropTypes expects string.
- Browser console also reports invalid table nesting: `<tr>` cannot appear as a child of `<td>`.

Impact:

- Accessibility and table semantics are degraded.
- The warning is separate from the backend 500 and should be fixed after data loads.

Recommended slice:

- Once `/services` API works, fix ServiceCatalog table column/title and row rendering semantics.

### P3: Overview section is overloaded

Evidence:

- Overview includes dashboard, analytics, webhooks, reports, system, cloud printing, medical equipment, and GraphQL.

Impact:

- Admin sidebar feels like a mixed operations bucket rather than a task-oriented overview.

Recommended slice:

- After functional fixes, regroup webhooks/GraphQL under integrations and cloud/equipment under operations/devices.

## Non-Findings

- Browser QA did not find login redirects, forbidden pages, not-found pages, unnamed icon-only buttons, or horizontal overflow across the audited routes/viewports.
- This does not prove every create/edit/delete action works; the audit did not mutate data.
