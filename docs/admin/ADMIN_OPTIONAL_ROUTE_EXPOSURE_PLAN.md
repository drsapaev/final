# Admin Optional Route Exposure Plan

Date: 2026-06-01

This document is the docs-only decision gate for optional Admin route exposure
after the AdminPanel route-owner cleanup. It does not expose routes by itself.
It defines when notification or Telegram subroutes are worth adding and what
proof is required before runtime changes.

## Current Decision

Do not expose additional notification or Telegram admin routes by default.
Expose a route only when there is a concrete Admin workflow that benefits from
a direct URL, route-specific heading, and route-specific browser smoke.

## Source Maps

- Notification channel ownership:
  `docs/admin/ADMIN_NOTIFICATION_ROUTE_CHANNELS.md`
- Telegram surface ownership:
  `docs/admin/ADMIN_TELEGRAM_ROUTE_SURFACES.md`
- Route ownership map:
  `docs/admin/ADMIN_ROUTE_OWNERSHIP.md`

## Exposure Candidates

| Candidate | Current status | Allowed next step | Must not do |
| --- | --- | --- | --- |
| FCM admin route | Hidden inside notification tooling | Optional route PR only if Admin needs direct FCM operations access | Do not merge into Email/SMS route without channel boundary proof |
| Registrar notification route | Hidden inside notification tooling | Optional route PR only if Admin needs direct registrar-alert operations access | Do not change delivery/read-state semantics |
| Telegram operational route | Already visible at `/admin/integrations/telegram` | Add browser/action smoke before changing behavior | Do not absorb token/storage/migration work casually |
| Telegram settings route | Already direct at `/admin/telegram-settings` | Keep separate from operational route unless a route contract PR proves consolidation | Do not hide token/config actions behind a generic notification surface |

## Minimum Runtime PR Shape

Any route exposure must be one small PR for one route family:

1. Add or adjust one route registry entry.
2. Add route contract coverage for the new route identity.
3. Add Admin-auth browser smoke for:
   - route shell;
   - visible heading;
   - no login/forbidden redirect;
   - no initial critical API 4xx/5xx;
   - no horizontal overflow at the smoke viewport.
4. Prove non-Admin behavior is unchanged or explicitly out of scope.
5. Include a rollback note in the PR body.

## Required Boundaries

- `/admin/notifications` remains Email/SMS unless a dedicated PR changes the
  channel map.
- FCM and registrar notification routes must name their channel and owner.
- Telegram operational and settings routes remain separate unless a dedicated
  route contract PR proves safe consolidation.
- Telegram DB, token storage, SQLAlchemy, and Alembic tasks follow DB/storage
  ownership first; route docs do not override migration rules.
- No route exposure PR may require live Telegram credentials, FCM production
  credentials, production secrets, or live external message delivery.

## Decision Checklist

Before opening an exposure PR, answer:

- Which Admin workflow is blocked by the missing direct route?
- Which channel or Telegram surface owns the route?
- Which component will be the direct route owner?
- Which existing route stays canonical?
- Which browser smoke proves the route does not render a generic placeholder?
- Which actions are intentionally not exposed?

## Safe Follow-Up PRs

### Notification FCM Route

Only if needed:

- route: `/admin/fcm-notifications`
- owner: notification FCM channel
- required proof: route contract + Admin browser smoke + no Email/SMS regression

### Notification Registrar Route

Only if needed:

- route: `/admin/registrar-notifications`
- owner: registrar operational alert channel
- required proof: route contract + Admin browser smoke + no delivery semantics change

### Telegram Action Smoke

Recommended before any route consolidation:

- route: `/admin/integrations/telegram`
- route: `/admin/telegram-settings`
- proof: browser-visible heading, route shell, primary action labels, no critical initial API errors, no secret/token leak

## Stop Conditions

- Stop if the change needs backend notification schema changes.
- Stop if route ownership is ambiguous.
- Stop if the route would collapse Email/SMS, FCM, registrar, and Telegram into
  one generic screen without channel-specific headings and actions.
- Stop if DB/migration/storage ownership appears; create a separate DB plan.
