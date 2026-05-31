# Admin Panel Deep Audit: Duplicate Functions

Date: 2026-06-01

Mode: audit-only. No runtime code changed.

## High-Risk Duplicate / Split Owners

### Analytics

Evidence:

- `frontend/src/routing/routeRegistry.js` maps `/admin/analytics` to `AnalyticsPage`.
- `frontend/src/pages/AdminPanel.jsx` still has `case 'analytics': return <AnalyticsDashboard />`.

Risk:

- Two analytics implementations can diverge.
- The AdminPanel branch is likely unreachable for the canonical route, which makes future fixes easy to put in the wrong component.

Recommendation:

- Pick one canonical analytics owner.
- If `AnalyticsPage` is canonical, remove or document the AdminPanel branch in a later runtime cleanup PR.

### Settings

Evidence:

- `frontend/src/routing/routeRegistry.js` maps `/admin/settings` to `Settings`.
- `frontend/src/pages/AdminPanel.jsx` still has `case 'settings': return <UnifiedSettings />`.
- Hidden/contextual routes such as `/admin/clinic-settings`, `/admin/queue-settings`, `/admin/payment-providers`, `/admin/wizard-settings`, and `/admin/display-settings` also route through `UnifiedSettings`.

Risk:

- Settings behavior can be patched in the wrong component.
- Hidden settings routes may lose route-specific context if everything collapses into a generic view.

Recommendation:

- Define a canonical settings shell.
- Make contextual settings routes pass explicit section/tab state rather than relying on a generic default.

### Telegram

Evidence:

- `/admin/integrations/telegram` maps to standalone `TelegramManager`.
- `/admin/telegram-settings` maps through `AdminPanel` to `UnifiedTelegramManagement`.
- `UnifiedTelegramManagement` wraps `TelegramBotManager` and `TelegramSettings`.

Risk:

- Bot API/webhook UX fixes can land in one Telegram surface while users enter through the other.
- This is especially risky because Telegram work also has DB/security/token ownership rules.

Recommendation:

- Keep Telegram Bot API/UX as one explicit route owner.
- Do not let Telegram UI skill or route cleanup override DB/Alembic ownership rules.

### Notifications

Evidence:

- `/admin/notifications` maps to `EmailSMSManager`.
- `AdminPanel` has `fcm-notifications` and `registrar-notifications` branches that render `UnifiedNotifications`.

Risk:

- Notification catalog, FCM, registrar-notification, and anti-noise policies can drift.
- User-facing entry points may show different controls for the same notification domain.

Recommendation:

- Define one notification admin shell with explicit subroutes/tabs.
- Preserve notification catalog/settings ownership boundaries.

### User Management

Evidence:

- `/admin/users` renders `UnifiedUserManagement`.
- `/admin/advanced-users` renders standalone `UserManagement`.
- `UnifiedUserManagement` also contains a local `AdminTabs` implementation.

Risk:

- Two user-management surfaces can conflict on permissions, exports, transfer, and group permission UX.

Recommendation:

- Decide whether `/admin/advanced-users` is an intentional advanced mode or legacy alias.
- If intentional, document what only belongs there.

## Lower-Risk Duplication / Design Drift

### Repeated local AdminTabs

Evidence:

- `UnifiedTelegramManagement.jsx`
- `UnifiedNotifications.jsx`
- `UnifiedAITools.jsx`
- `UnifiedFinance.jsx`
- `UnifiedUserManagement.jsx`

Risk:

- Tabs look similar but are not the same component.
- Several wrappers use hardcoded colors such as `#3b82f6` and raw `rgba(...)`, bypassing design tokens.

Recommendation:

- Extract or reuse one admin tab primitive in a later UI-system PR.
- Do not refactor all admin surfaces in one PR.

### Deprecated departments alias

Evidence:

- `AdminPanel.jsx` has a `departments` branch that renders `QueueProfilesManager`.
- Comment says DepartmentManagement is deprecated and queue profiles are the SSOT.

Risk:

- Low if this remains documented.

Recommendation:

- Keep the alias only if external links still use it.
- Add route-registry documentation if the alias remains user-visible.

## Fix Slice Order

1. Fix broken route APIs first: services, reports, file management.
2. Pick canonical owners for duplicated Telegram/notifications/settings/user-management.
3. Normalize admin tab primitive only after owners are clear.
4. Reconsider sidebar grouping after functional issues are green.
