# Admin Route Ownership

Date: 2026-06-01

This file is the canonical ownership map for AdminPanel route families. It
exists to prevent future agents from treating duplicate-looking admin screens as
interchangeable without checking the intended owner first.

## Rules

- Route ownership beats component similarity. Two screens that render similar
  text are not duplicates until their business owner is the same.
- Canonical routes should keep the broad workflow. Contextual routes should
  open one explicit section, tab, or settings surface.
- Do not remove, redirect, or merge an admin route without a small PR that names
  the canonical owner and browser-smokes both the source and target route.
- Admin destructive actions need explicit confirmation and role proof before
  any route consolidation.
- Hidden/contextual routes must not silently render generic settings content.

## Route Family Matrix

| Family | Canonical owner | Canonical route | Contextual / related routes | Boundary |
| --- | --- | --- | --- | --- |
| Dashboard | `admin.dashboard` | `/admin` | none | Operational overview only. Do not add deep settings or CRUD workflows here. |
| Analytics | `admin.analytics` | `/admin/analytics` | `AdminPanel` internal analytics case | `/admin/analytics` owns analytics dashboards. Internal cases are legacy wrappers unless a route test proves otherwise. |
| Reports | `admin.reports` | `/admin/reports` | reports export/files endpoints | Reports owns generated summaries/exports. It must not become generic analytics navigation. |
| Users | `admin.users` | `/admin/users` | `/admin/advanced-users` | `/admin/users` is the normal user-management entry. `/admin/advanced-users` is an advanced/legacy entry until explicitly merged or redirected. |
| Doctors | `admin.doctors` | `/admin/doctors` | doctor-related settings only by explicit link | Doctor CRUD belongs here. Doctor queues and specialty panels do not. |
| Services | `admin.services` | `/admin/services` | legacy departments/queue profiles | Service catalog is the service truth. Queue cabinet/profile configuration stays separate unless a PR explicitly merges ownership. |
| Queue cabinets | `admin.queue_cabinets` | `/admin/queue-cabinet-management` | `/admin/queue-settings`, `/admin/display-settings` | Cabinet/profile operations are not display-board settings and not general queue policy. |
| Patients | `admin.patients` | `/admin/patients` | patient documents/files | Patient admin screens must not replace registrar workflow screens. |
| Appointments | `admin.appointments` | `/admin/appointments` | `/admin/user-select` | Appointment support is separate from registrar live workflow. |
| Finance | `admin.finance` | `/admin/finance` | `/admin/payment-providers`, `/admin/benefit-settings` | Finance owns transactions/accounting. Provider and benefit settings are explicit settings subroutes. |
| Clinic management | `admin.clinic_management` | `/admin/clinic-management` | `/admin/clinic-settings` | Management owns clinic entities. Clinic settings owns static configuration. |
| Settings | `admin.settings` | `/admin/settings` | `/admin/security`, `/admin/ai-settings`, `/admin/wizard-settings`, `/admin/payment-providers`, `/admin/queue-settings`, `/admin/display-settings`, `/admin/benefit-settings`, `/admin/clinic-settings` | `/admin/settings` is generic settings. Contextual routes must open their named section directly. |
| Security | `admin.security` | `/admin/security` | `SecuritySettings`, security/audit reports | Security route owns password/security controls. It must not default to generic clinic settings. |
| Telegram | `admin.telegram` | `/admin/integrations/telegram` | `/admin/telegram-settings` | Integration route owns operational bot/webhook/contract work. Settings route owns token/settings configuration only. |
| Notifications | `admin.notifications` | `/admin/notifications` | `UnifiedNotifications`, FCM, registrar notifications | Email/SMS route owns current sidebar entry. Channel-specific notification settings require explicit route map before consolidation. |
| Files | `admin.files` | `/admin/file-management` | patient/visit document viewers | File management owns admin-wide file listing and storage actions. Clinical document viewers remain patient/visit scoped. |
| Audit | `admin.audit` | `/admin/audit` | security audit summaries | Audit route owns immutable audit/event review, not security configuration. |

## Current Duplicate Decisions

### Users

Keep both routes for now:

- `/admin/users`: canonical day-to-day user-management route.
- `/admin/advanced-users`: advanced/legacy route that must not diverge silently.

Next fix slice should either turn `/admin/advanced-users` into an explicit
advanced tab/wrapper or redirect it to a tested canonical screen.

### Telegram

Keep operational and settings routes separate:

- `/admin/integrations/telegram`: operational Telegram manager for bot health,
  webhook/contract, onboarding, and runtime operations.
- `/admin/telegram-settings`: Telegram settings/token/configuration surface.

Migration, token-storage, and Alembic tasks still follow DevBrain migration and
Telegram security rules before any UI route decision.

### Notifications

Treat notification routes as channel-specific until a later PR creates a full
notification map:

- `/admin/notifications`: current Email/SMS manager.
- `UnifiedNotifications`: FCM and registrar notification surfaces.

Do not merge them until each channel has owner, settings, runtime policy, and
negative-noise validation.

### Settings

Generic settings and direct settings routes are intentionally separate:

- `/admin/settings`: broad settings landing.
- Direct routes such as `/admin/security` and `/admin/payment-providers`: must
  open the exact named section.

Any future settings refactor must preserve route-specific browser smoke for all
contextual routes.

## Required Validation For Route Consolidation

Before changing any route family above:

1. Browser-smoke the current canonical route and the route being changed.
2. Prove Admin auth works and non-target roles are unchanged or out of scope.
3. Check for API 4xx/5xx on initial load.
4. Check the visible heading/content matches the route name.
5. Confirm primary actions still exist and destructive actions still require
   confirmation.
6. Update route contract tests or add a docs-only rationale if no test exists.

## Known Follow-Ups

- Decide `/admin/advanced-users` alias/wrapper behavior.
- Create notification channel ownership map before merging Email/SMS, FCM, and
  registrar notification settings.
- Decide whether analytics internal AdminPanel wrappers are legacy and can be
  removed.
- Add route contract tests for duplicate families after the canonical map is
  accepted.
