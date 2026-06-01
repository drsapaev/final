# AdminPanel Deep Audit Post-Fix Status

Date: 2026-06-01

This is a status addendum for the AdminPanel deep audit. It preserves the
original audit as baseline evidence and records the small PRs merged afterward.

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
- Contextual settings routes deep-link to their intended screens:
  - `/admin/security?section=security`
  - `/admin/ai-settings?section=ai-settings`
  - `/admin/wizard-settings?section=wizard-settings`
  - `/admin/payment-providers?section=payment-providers`
  - `/admin/benefit-settings?section=benefit-settings`
  - `/admin/clinic-settings?section=clinic-settings`
  - `/admin/queue-settings?section=queue-settings`
  - `/admin/display-settings?section=display-settings`
  - `/admin/telegram-settings?section=settings`

## Remaining Backlog

### P1

- No open P1 admin route ownership item after the current user,
  notification, and Telegram guardrails. New runtime route exposure still needs
  a dedicated plan and browser smoke.

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
- `AdminPanel.jsx` remains a broad route switch plus implementation container,
  although `/admin/telegram-settings` has been extracted as the first small
  contextual route slice.
- Remaining heading-semantics work is now primarily browser/visual QA, not route
  chrome contract coverage.

## Recommended Next PR Slices

1. `refactor(admin): extract one AdminPanel route family`
   - Only after a specific family is selected.
   - One family per PR.
2. `test(admin): add browser-visible heading smoke for admin route families`
   - Route chrome headings are now covered for operations, integrations,
     management, and contextual admin routes.
   - Continue with browser-visible headings only when a route family is selected.
3. `docs(admin): plan optional notification or Telegram route exposure`
   - Only if a real user workflow needs direct FCM/registrar/Telegram subroutes.
   - No runtime exposure without browser smoke.

## Stop Conditions

- Do not merge user-management routes without naming the canonical owner and preserving advanced workflows.
- Do not expose notification subroutes without channel ownership and role/browser smoke.
- Do not move Telegram token/security work between operational and settings surfaces without a Telegram-specific contract review.
- Do not broaden an AdminPanel fix into a general redesign.
