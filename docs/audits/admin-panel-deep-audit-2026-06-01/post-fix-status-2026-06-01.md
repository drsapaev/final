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

## Current Verified Status

- `/admin/reports` loads without the previous daily-summary 500 in local `clinic_dev` smoke.
- `/admin/file-management` uses the canonical file endpoints and no longer produces the previous 401/422 sequence in local smoke.
- `/admin/services` no longer produces the `MacOSTable` column-title PropTypes warning.
- `/admin/graphql-explorer` no longer produces the `textareaStyle` unknown DOM prop warning.
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

- User-management duplicate route family:
  - `/admin/users` is the canonical day-to-day user management route.
  - `/admin/advanced-users` remains an advanced/legacy route.
  - Next fix must either make the relationship explicit in UI copy/tests or intentionally alias/wrap one route.
- Notification route family:
  - `/admin/notifications` currently owns Email/SMS.
  - `UnifiedNotifications` owns FCM/registrar notification surfaces but has no dedicated route map.
  - Channel ownership is tracked in `docs/admin/ADMIN_NOTIFICATION_ROUTE_CHANNELS.md`.
  - Do not expose or merge notification subroutes until a route implementation PR is browser-smoked.
- Telegram route family:
  - `/admin/integrations/telegram` remains the operational integration route.
  - `/admin/telegram-settings` now opens settings content.
  - Future token/security changes must name which surface owns the work before editing.

### P2

- Overview navigation group is still overloaded with operational/integration tooling:
  - webhooks
  - cloud printing
  - medical equipment
  - GraphQL API
- `AdminPanel.jsx` remains a broad route switch plus implementation container.
- Some routes still have weak heading semantics and should get route-specific heading checks before UI redesign.

## Recommended Next PR Slices

1. `docs(admin): add notification route channel map`
   - Docs/test-first decision.
   - No runtime route exposure yet.
2. `test(admin): guard duplicate user route ownership`
   - Add route contract around `/admin/users` and `/admin/advanced-users`.
   - No consolidation until a small browser-smoked implementation plan exists.
3. `docs(admin): plan overview navigation regrouping`
   - Decide whether operational tooling moves out of "Overview" or the section is renamed.
4. `refactor(admin): extract one AdminPanel route family`
   - Only after a specific family is selected.
   - One family per PR.

## Stop Conditions

- Do not merge user-management routes without naming the canonical owner and preserving advanced workflows.
- Do not expose notification subroutes without channel ownership and role/browser smoke.
- Do not move Telegram token/security work between operational and settings surfaces without a Telegram-specific contract review.
- Do not broaden an AdminPanel fix into a general redesign.
