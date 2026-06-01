# Admin Telegram Route Surfaces

Date: 2026-06-01

This file defines the admin Telegram route boundary before any token,
webhook, storage, or bot UX work. The goal is to prevent future fixes from
moving Telegram behavior between similar-looking admin screens without naming
the owning surface.

## Current Decision

Keep the Telegram admin routes separate:

- `/admin/integrations/telegram` is the operational Telegram integration
  surface.
- `/admin/telegram-settings` is the contextual settings/configuration surface.
- Both routes are owned by `admin.telegram`.
- Telegram Mini App patient routes remain separate under `telegram.mini_app`.

## Surface Matrix

| Surface | Route | Component path | Owner | Entry | Owns |
| --- | --- | --- | --- | --- | --- |
| Operational integration | `/admin/integrations/telegram` | `frontend/src/components/TelegramManager.jsx` | `admin.telegram` | sidebar/menu | Bot status, webhook visibility/actions, templates, Telegram users, test messages, operational troubleshooting. |
| Settings/configuration | `/admin/telegram-settings` | `frontend/src/components/admin/TelegramSettings.jsx` | `admin.telegram` | contextual/direct | Token/config form, webhook-info/settings stats, setup instructions, settings save/test actions. |
| Unified admin helper | no public route | `frontend/src/components/admin/UnifiedTelegramManagement.jsx` | internal helper | unrouted | Internal tab helper for bot/settings content. It is not the canonical sidebar route. |
| Patient Mini App | `/telegram/mini-app/patient` | `frontend/src/pages/TelegramMiniAppPatientShell.jsx` | `telegram.mini_app` | public mini-app | Telegram WebApp patient UX. It must not inherit admin route assumptions. |

## Routing Rules

- Do not merge `/admin/integrations/telegram` and `/admin/telegram-settings`
  without a dedicated route contract PR and browser smoke.
- Do not move token/security/storage tasks into general notification routes.
- Do not use Telegram bot builder guidance for Alembic or SQLAlchemy storage
  ownership until DB ownership is ruled out.
- If a task mentions Telegram plus Alembic, SQLAlchemy, table missing,
  Postgres SSOT, token storage, or migration, DB/migration ownership wins first.
- If a task changes Bot API/webhook UX only, use the operational integration
  surface unless the change is purely saved configuration.

## Required Validation Before Runtime Changes

Before editing Telegram runtime UI or backend code:

1. Name the target surface: operational integration, settings, mini app, or DB
   migration/storage.
2. Run the route contract tests for admin Telegram routes.
3. Browser-smoke the affected route with Admin auth if it is an admin surface.
4. Confirm no token, webhook secret, or production credential is printed.
5. Confirm notification route ownership remains separate.
6. For storage/migration work, create a new Alembic revision instead of editing
   already-applied migrations.

## Stop Conditions

- Stop if the change needs live Telegram credentials, production webhook
  registration, or production secrets.
- Stop if token/security ownership is unclear.
- Stop if the task is actually a DB migration/storage task.
- Stop if a route consolidation would hide bot status, token settings, webhook
  controls, or Telegram Mini App patient behavior.
