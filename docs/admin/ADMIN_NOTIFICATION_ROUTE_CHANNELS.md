# Admin Notification Route Channel Map

Date: 2026-06-01

This file defines admin notification route ownership before any runtime route
merge, redirect, or sidebar change. It exists because several notification UI
surfaces look related but operate different channels, backends, and risk
profiles.

## Current Decision

Keep notification channels separate until a later implementation PR proves a
safe consolidation path with route tests and browser smoke.

## Channel Matrix

| Channel / surface | Current route | Current component | Backend/API owner | Current status | Boundary |
| --- | --- | --- | --- | --- | --- |
| Email and SMS operations | `/admin/notifications` | `components/notifications/EmailSMSManager.jsx` | `/api/v1/email-sms/*` | Canonical sidebar route | Owns email/SMS tests, templates, statistics, and bulk messaging. It must not silently absorb push/registrar policy. |
| FCM push operations | no public admin route yet | `components/admin/UnifiedNotifications.jsx` -> `FCMManager` | `/api/v1/fcm/*` | Hidden/unrouted admin surface | Owns FCM status, user device tokens, and push test/send tools. Do not expose without push-channel route tests and Admin browser smoke. |
| Registrar operational alerts | no public admin route yet | `components/admin/UnifiedNotifications.jsx` -> `RegistrarNotificationManager` | `/api/v1/registrar/notifications/*` | Hidden/unrouted admin surface | Owns registrar system alerts, daily summaries, registrar stats, and registrar-only recipient targeting. Do not merge with Email/SMS templates. |
| In-app notification center | role panels / notification center providers | `NotificationCenterContext`, `NotificationWebSocketContext`, `RoleNotificationCenter` | `/api/v1/notifications/*`, `/api/v1/ws/notifications/connect` | Runtime delivery/read-state surface | Owns inbox, unread counts, websocket delivery, read/seen/archive semantics. Admin route work must not change delivery semantics casually. |
| Telegram patient/admin notifications | Telegram admin routes and bot/webhook surfaces | `TelegramManager`, `TelegramSettings`, Telegram bot/webhook code | `/api/v1/telegram*`, Telegram webhook/services | Separate Telegram ownership | Owns Telegram consent, token/security, webhook, bot UX, and patient chat delivery. It is not part of Email/SMS/FCM route consolidation. |
| User notification preferences | user/profile management routes | user management/profile settings | `/api/v1/users/{id}/notifications`, preferences services | User preference policy | Owns per-user channel preferences, quiet hours, weekend notification rules, and anti-noise settings. It must be checked before bulk-send or runtime policy changes. |

## Route Policy

- `/admin/notifications` remains the canonical visible admin route for Email/SMS.
- Do not create `/admin/fcm-notifications` or `/admin/registrar-notifications`
  as runtime routes until a dedicated PR adds:
  - route registry entries;
  - Admin-only access proof;
  - direct-route browser smoke;
  - no 4xx/5xx on initial load;
  - clear visible heading/content proof;
  - route contract tests.
- Do not make `UnifiedNotifications` the sidebar route until the route owner
  and default tab are explicit.
- Do not route Telegram notification settings through this channel map.
  Telegram token/security and webhook work follows the Telegram ownership map
  and DevBrain Telegram guardrails.
- Do not change notification delivery/read-state behavior from an admin route
  cleanup PR.

## Required Validation Before Runtime Changes

Before exposing, merging, redirecting, or renaming notification routes:

1. Browser-smoke `/admin/notifications`.
2. Browser-smoke the proposed FCM/registrar route or tab deep link.
3. Confirm Admin auth works.
4. Confirm non-Admin behavior is unchanged or out of scope with a stated reason.
5. Check for initial-load API 4xx/5xx.
6. Check console warnings/errors.
7. Verify visible route heading and primary actions match the channel.
8. Run route contract tests for the changed route family.
9. Confirm delivery semantics remain unchanged:
   - unread count;
   - seen/read/archive;
   - websocket reconnect/resync;
   - user preferences / quiet hours / anti-noise policy.

## Safe Next Slices

### Slice A: Route Contract Guardrail

Add tests proving:

- `/admin/notifications` remains `EmailSMSManager`.
- FCM and registrar notification surfaces are intentionally not public routes
  until a route-map implementation PR exists.
- `UnifiedNotifications` is an internal aggregator, not the canonical sidebar
  owner.

### Slice B: Optional Hidden Route Exposure

If Admin needs direct URLs for FCM or registrar notifications, create a small PR
that adds only one route at a time:

- `/admin/fcm-notifications?section=fcm`
- or `/admin/registrar-notifications?section=registrar-notifications`

Each route must have a matching owner, test, browser smoke, and rollback note.

### Slice C: Unified Notification Settings

Only after the channel routes are proven, decide whether to create a single
unified notifications landing page. It must show channel boundaries clearly and
must not hide Email/SMS, FCM, registrar, Telegram, or user preference ownership.

## Stop Conditions

- Stop if a notification route change needs backend notification schema or
  delivery policy changes.
- Stop if channel ownership is unclear.
- Stop if FCM credentials or live external messaging are required for local QA.
- Stop if a route consolidation would remove Email/SMS, FCM, or registrar
  primary actions without an explicit replacement.
