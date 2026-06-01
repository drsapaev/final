# AdminPanel Deep Audit Post-Fix Status

Date: 2026-06-01

This is a status addendum for the AdminPanel deep audit. It preserves the
original audit as baseline evidence and records the small PRs merged afterward.

## Final Route-Owner Closeout

As of PR #1571, no active route in `frontend/src/routing/routeRegistry.js`
renders the legacy `AdminPanel` component owner. `frontend/src/pages/AdminPanel.jsx`
has been deleted after the last extraction-bound admin routes were moved to
direct route owners and the route contract was updated to prevent regression.

Historical audit files below still mention `AdminPanel` because they are baseline
evidence from before the route-owner rollout. Current source-of-truth checks are:

- `rg "component: 'AdminPanel'" frontend/src/routing/routeRegistry.js` returns no matches.
- `rg "AdminPanel\.jsx|pages/AdminPanel" frontend/src` returns no active source references.
- `npm.cmd run test:run -- src/routing/__tests__/routeContract.test.js src/routing/__tests__/routeOwnershipEnforcement.test.js src/__tests__/notificationGuardrails.test.js` passes.

## Merged Fix Slices

| PR | Status | Scope | Result |
| --- | --- | --- | --- |
| #1504 | merged | `/admin/reports` daily summary backend totals | Fixed the 500 from `GET /api/v1/reports/daily-summary`; report totals now derive from invoices/services instead of nonexistent `Visit` fields. |
| #1505 | merged | `/admin/file-management` frontend API paths | Fixed file list/statistics calls by using canonical `/api/v1/files/` and `/api/v1/files/statistics`; removed redirect/auth-loss and `/stats` route mismatch. |
| #1506 | merged | docs route ownership map | Added canonical route ownership boundaries for users, settings, Telegram, notifications, finance, files, audit, and related admin families. |
| #1507 | merged | `MacOSTable` header PropTypes | Fixed `/admin/services` table warning by allowing React node headers. |
| #1508 | merged | `MacOSTextarea` DOM prop handling | Fixed `/admin/graphql-explorer` React unknown-prop warning by consuming `textareaStyle` inside the UI primitive. |
| #1509 | merged | AdminPanel route-state guardrail test | Added a test protecting contextual route section mappings and Telegram settings routing. |
| #1511 | merged | notification route channel map | Documented Email/SMS, FCM, registrar, in-app, Telegram, and preference ownership boundaries. |
| #1513 | merged | duplicate user route guardrail | Added route contract coverage for `/admin/users` and `/admin/advanced-users`. |
| #1514 | merged | overview navigation grouping plan | Documented the staged `Overview` / `Operations` / `Integrations` split. |
| #1516 | merged | overview route section guardrail | Added route contract coverage before moving sidebar sections. |
| #1518 | merged | overview sidebar regrouping | Moved system/cloud-printing/medical-equipment to `Операции` and webhooks/GraphQL to `Интеграции`. |
| #1521 | merged | advanced user route wrapper | Made `/admin/advanced-users` explicit as an advanced/legacy surface wrapping `UserManagement`, while `/admin/users` remains the canonical day-to-day user route. |
| #1523 | merged | notification route ownership guardrail | Added route contract proof that `/admin/notifications` remains Email/SMS and FCM/registrar notification routes stay unrouted until deliberately exposed. |
| #1529 | merged | AI settings direct route | Routed `/admin/ai-settings` directly to `AISettings`, while leaving the old AdminPanel query branch as a compatibility path for a later cleanup. |
| #1531 | merged | phone verification direct route | Routed `/admin/phone-verification` directly to `PhoneVerificationManager`, while leaving the old AdminPanel switch branch as a compatibility path for a later cleanup. |
| #1534 | merged | activation direct route | Routed `/admin/activation` directly to `ActivationSystem`, while leaving the old AdminPanel switch branch as a compatibility path for a later cleanup. |
| #1536 | merged | clinic management direct route | Routed `/admin/clinic-management` directly to `ClinicManagement`, while leaving the old AdminPanel switch branch as a compatibility path for a later cleanup. |
| #1539 | merged | queue cabinets direct route | Routed `/admin/queue-cabinet-management` directly to `QueueCabinetManagement`, while leaving the old AdminPanel switch branch as a compatibility path for a later cleanup. |
| #1541 | merged | clinic settings direct route | Routed `/admin/clinic-settings` directly to `UnifiedSettings`, while leaving the old AdminPanel switch branch as a compatibility path for a later cleanup. |
| #1544 | merged | contextual settings direct routes | Routed hidden contextual settings routes for benefit, wizard, payment providers, queue, and display settings directly to `UnifiedSettings`, while leaving old AdminPanel switch branches as compatibility paths for later cleanup. |
| #1546 | merged | operations direct routes | Routed `/admin/system`, `/admin/cloud-printing`, and `/admin/medical-equipment` directly to their route-specific components. |
| #1548 | merged | integrations direct routes | Routed `/admin/webhooks` and `/admin/graphql-explorer` directly to their route-specific components. |
| #1550 | merged | reports direct route | Routed `/admin/reports` directly to `UnifiedReports`. |
| #1552 | merged | users direct route | Routed `/admin/users` directly to `UnifiedUserManagement` while preserving `/admin/advanced-users` as the advanced/legacy user-management surface. |
| #1553 | merged | all-free direct route | Routed `/admin/all-free` directly to `AllFreeApproval` and added standalone management route contract coverage. |
| #1555 | merged | security settings direct route | Routed `/admin/security` directly to `UnifiedSettings` and made `UnifiedSettings` derive contextual sections from canonical `/admin/<section>` paths. |
| #1563 | merged | dashboard direct route | Routed `/admin` directly to `AdminDashboard`. |
| #1564 | merged | finance direct route | Routed `/admin/finance` directly to `UnifiedFinance`. |
| #1566 | merged | doctors direct route | Routed `/admin/doctors` directly to `AdminDoctors`. |
| #1568 | merged | patients direct route | Routed `/admin/patients` directly to `AdminPatients`. |
| #1569 | merged | appointments direct route | Routed `/admin/appointments` directly to `AdminAppointments`. |
| #1570 | merged | legacy registration cleanup | Removed the unused `AdminPanel` lazy registration from `App.jsx` and added a no-legacy-admin-route invariant. |
| #1571 | merged | legacy file cleanup | Deleted the unused `AdminPanel.jsx` file and stale tests/audit references that tried to read it. |

## Current Verified Status

- `/admin/reports` loads without the previous daily-summary 500 in local `clinic_dev` smoke.
- `/admin/file-management` uses the canonical file endpoints and no longer produces the previous 401/422 sequence in local smoke.
- `/admin/services` no longer produces the `MacOSTable` column-title PropTypes warning.
- `/admin/graphql-explorer` no longer produces the `textareaStyle` unknown DOM prop warning.
- `/admin/users` and `/admin/advanced-users` have route contract coverage for
  their intentional canonical vs advanced split.
- `/admin/advanced-users` now renders an explicit advanced/legacy notice before
  the shared user table, so it no longer looks like an unlabelled duplicate of
  `/admin/users`.
- `/admin/notifications` is guarded as the Email/SMS admin route; FCM and
  registrar notification surfaces remain internal until a dedicated route PR.
- Telegram admin surface policy is documented in
  `docs/admin/ADMIN_TELEGRAM_ROUTE_SURFACES.md`.
- `/admin/telegram-settings` is a direct `TelegramSettings` route, reducing one
  contextual settings branch from the broad `AdminPanel.jsx` switch.
- `/admin/ai-settings` is a direct `AISettings` route, reducing one visible
  settings route from the broad `AdminPanel.jsx` switch while preserving the AI
  sidebar disclaimer.
- `/admin/phone-verification` is a direct `PhoneVerificationManager` route,
  reducing another visible system route from the broad `AdminPanel.jsx` switch.
- `/admin/activation` is a direct `ActivationSystem` route, reducing another
  visible licensing route from the broad `AdminPanel.jsx` switch while
  preserving `/activation` as a legacy redirect.
- `/admin/clinic-management` is a direct `ClinicManagement` route, reducing
  another visible operations route from the broad `AdminPanel.jsx` switch while
  preserving its sidebar identity.
- `/admin/queue-cabinet-management` is a direct `QueueCabinetManagement` route,
  reducing another queue operations route from the broad `AdminPanel.jsx`
  switch while preserving its sidebar identity.
- `/admin/clinic-settings` is a direct `UnifiedSettings` route, reducing one
  contextual settings route from the broad `AdminPanel.jsx` switch while
  preserving its hidden/direct route identity.
- Hidden contextual settings routes for benefit settings, wizard settings,
  payment providers, queue settings, and display settings are now direct
  `UnifiedSettings` routes, preserving `nav: false` and reducing more broad
  `AdminPanel.jsx` routing.
- `/admin/security` is now a direct `UnifiedSettings` route. `UnifiedSettings`
  now derives route-owned sections from canonical admin paths, so contextual
  settings routes no longer require `?section=...` to render their intended
  settings panel.
- `/admin/system`, `/admin/cloud-printing`, `/admin/medical-equipment`,
  `/admin/webhooks`, `/admin/graphql-explorer`, `/admin/reports`,
  `/admin/users`, and `/admin/all-free` are now direct route owners instead of
  broad `AdminPanel.jsx` switch branches.
- No `AdminPanel`-owned routes remain in `routeRegistry.js`.
- The old `AdminPanel.jsx` implementation file has been deleted. Future admin
  route work should start from the direct route owner component, not from the
  deleted broad switch.
- Admin sidebar grouping is now:
  - `Overview`: dashboard, analytics, reports
  - `Операции`: system, cloud printing, medical equipment
  - `Интеграции`: webhooks, GraphQL API
- Operations and integrations routes have route-contract coverage for
  route-specific chrome headings, so future UI cleanup must keep distinct page
  identities instead of collapsing them into a generic AdminPanel surface.
- Management and contextual admin routes have route-contract coverage for
  route-specific chrome headings, including hidden direct settings routes, so
  future extraction work must preserve distinct page identities.
- Contextual settings routes deep-link to their intended screens by path first:
  - `/admin/security`
  - `/admin/wizard-settings`
  - `/admin/payment-providers`
  - `/admin/benefit-settings`
  - `/admin/clinic-settings`
  - `/admin/queue-settings`
  - `/admin/display-settings`
  - `/admin/telegram-settings`

## Remaining Backlog

### P1

- No open P1 admin route ownership item after the current settings, user,
  notification, Telegram, operations, integrations, reports, all-free, and
  security route slices. New runtime route exposure still needs a dedicated plan
  and browser smoke.

### P2

- Overview navigation grouping has a staged route policy:
  - `Overview`: dashboard, analytics, reports
  - `Operations`: system, cloud printing, medical equipment
  - `Integrations`: webhooks, GraphQL API
  - Runtime grouping and evidence are recorded in `docs/admin/ADMIN_OVERVIEW_NAVIGATION_GROUPING_PLAN.md`.
- Notification direct FCM/registrar route exposure remains optional and must
  follow `docs/admin/ADMIN_NOTIFICATION_ROUTE_CHANNELS.md`.
- Telegram route consolidation remains optional and must follow
  `docs/admin/ADMIN_TELEGRAM_ROUTE_SURFACES.md`.
- Route ownership cleanup is complete. Remaining admin work is now route-family
  QA, grouping polish, and browser-visible workflow verification, not broad
  `AdminPanel.jsx` extraction.
- Remaining heading-semantics work is now primarily browser/visual QA, not route
  chrome contract coverage.

## Recommended Next PR Slices

1. `test(admin): add browser-visible heading smoke for admin route families`
   - Route chrome headings are now covered for operations, integrations,
     management, and contextual admin routes.
   - Continue with browser-visible headings only when a route family is selected.
2. `docs(admin): plan optional notification or Telegram route exposure`
   - Only if a real user workflow needs direct FCM/registrar/Telegram subroutes.
   - No runtime exposure without browser smoke.
3. `test(admin): add per-route action smoke for data-heavy admin screens`
   - Cover doctors, patients, appointments, services, and finance one route
     family at a time.
   - Keep API/RBAC behavior unchanged unless a route-specific finding proves a
     backend contract issue.

## Stop Conditions

- Do not merge user-management routes without naming the canonical owner and preserving advanced workflows.
- Do not expose notification subroutes without channel ownership and role/browser smoke.
- Do not move Telegram token/security work between operational and settings surfaces without a Telegram-specific contract review.
- Do not reintroduce `AdminPanel.jsx` as a broad route switch.
- Do not broaden a route-family fix into a general admin redesign.
- Do not collapse direct route owner components back into a generic admin
  surface.
