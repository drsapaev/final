# Admin Panel Deep Audit: Route / Section Matrix

Date: 2026-06-01

Mode: audit-only. No runtime code changed.

## Sources Inspected

- `AGENTS.md`
- `.cursorrules`
- `frontend/DESIGN_SYSTEM.md`
- `frontend/THEME_SYSTEM_GUIDE.md`
- `frontend/src/routing/routeRegistry.js`
- `frontend/src/routing/routeSelectors.js`
- `frontend/src/pages/AdminPanel.jsx`
- `frontend/src/components/admin/*`
- `frontend/src/components/files/FileManager.jsx`
- Browser QA against `clinic_dev`, backend `18000`, frontend `5173`

## Matrix

| Route | Registry section | Registry component | Runtime owner | Audit note |
| --- | --- | --- | --- | --- |
| `/admin` | Overview | `AdminPanel` | `admin.operations` | Dashboard route loads. |
| `/admin/analytics` | Overview | `AnalyticsPage` | `admin.analytics` | Separate page, while `AdminPanel` also has a dead `analytics` branch using `AnalyticsDashboard`. |
| `/admin/webhooks` | Overview | `AdminPanel` | `admin.integrations` | Route loads, but embeds `AdminRouteSwitcher current="dashboard"`, so local quick switcher marks dashboard active inside webhooks. |
| `/admin/reports` | Overview | `AdminPanel` | `admin.reports` | Route loads but daily summary API returns 500. |
| `/admin/system` | Overview | `AdminPanel` | `admin.system` | Route loads. Grouping under Overview is debatable because this is system operations. |
| `/admin/cloud-printing` | Overview | `AdminPanel` | `admin.operations` | Route loads. Grouping under Overview is debatable because this is device/ops management. |
| `/admin/medical-equipment` | Overview | `AdminPanel` | `admin.operations` | Route loads. Grouping under Overview is debatable because this is device/ops management. |
| `/admin/graphql-explorer` | Overview | `AdminPanel` | `admin.integrations` | Route loads; React warning for leaked `textareaStyle` prop. |
| `/admin/users` | Management | `AdminPanel` | `admin.users` | Uses `UnifiedUserManagement`; overlaps with `/admin/advanced-users`. |
| `/admin/doctors` | Management | `AdminPanel` | `admin.users` | Route loads. |
| `/admin/services` | Management | `AdminPanel` | `admin.catalog` | Service catalog route loads shell but service list API returns 500. |
| `/admin/queue-cabinet-management` | Management | `AdminPanel` | `admin.queue` | Route loads. |
| `/admin/patients` | Management | `AdminPanel` | `admin.patients` | Route loads. |
| `/admin/appointments` | Management | `AdminPanel` | `admin.scheduling` | Route loads. |
| `/admin/all-free` | Management | `AdminPanel` | `admin.operations` | Route loads. |
| `/admin/benefit-settings` | Contextual/no nav | `AdminPanel` | `admin.billing` | Hidden/contextual route uses `UnifiedSettings`; no sidebar active item. |
| `/admin/wizard-settings` | Contextual/no nav | `AdminPanel` | `admin.settings` | Hidden/contextual route uses `UnifiedSettings`; no sidebar active item. |
| `/admin/payment-providers` | Contextual/no nav | `AdminPanel` | `admin.billing` | Hidden/contextual route uses `UnifiedSettings`; no sidebar active item. |
| `/admin/clinic-management` | System | `AdminPanel` | `admin.operations` | Route loads. |
| `/admin/clinic-settings` | Contextual/no nav | `AdminPanel` | `admin.settings` | Hidden/contextual route uses `UnifiedSettings`; no sidebar active item. |
| `/admin/queue-settings` | Contextual/no nav | `AdminPanel` | `admin.queue` | Hidden/contextual route uses `UnifiedSettings`; no sidebar active item. |
| `/admin/ai-settings` | System | `AdminPanel` | `admin.ai` | Route loads through `UnifiedSettings`, while AI tool subroutes use `UnifiedAITools`. |
| `/admin/telegram-settings` | Contextual/no nav | `AdminPanel` | `admin.integrations` | Hidden/contextual route uses `UnifiedTelegramManagement`; overlaps with `/admin/integrations/telegram`. |
| `/admin/display-settings` | Contextual/no nav | `AdminPanel` | `admin.queue` | Hidden/contextual route uses `UnifiedSettings`; no sidebar active item. |
| `/admin/integrations/telegram` | System | `TelegramManager` | `admin.integrations` | Separate direct component; overlaps with AdminPanel Telegram management branches. |
| `/admin/notifications` | System | `EmailSMSManager` | `admin.notifications` | Separate direct component; overlaps with AdminPanel notification branches. |
| `/admin/phone-verification` | System | `AdminPanel` | `admin.integrations` | Route loads. |
| `/admin/activation` | System | `AdminPanel` | `admin.licensing` | Route loads. |
| `/admin/finance` | System | `AdminPanel` | `admin.billing` | Route loads through `UnifiedFinance`. |
| `/admin/settings` | System | `Settings` | `admin.settings` | Separate page, while `AdminPanel` also has a dead `settings` branch using `UnifiedSettings`. |
| `/admin/security` | System | `AdminPanel` | `admin.security` | Route loads through `UnifiedSettings`. |
| `/admin/audit` | System | `Audit` | `admin.audit` | Separate page; route loads. |
| `/admin/advanced-users` | System | `UserManagement` | `admin.users` | Separate page; overlaps with `/admin/users` `UnifiedUserManagement`. |
| `/admin/file-management` | System | `FileManager` | `admin.files` | Route loads shell but browser QA shows file API failures. |
| `/admin/user-select` | Contextual/no nav | `UserSelect` | `admin.users` | Hidden/contextual route; route loads. |

## Route Grouping Notes

- Overview currently includes operational/configuration surfaces (`system`, `webhooks`, `cloud-printing`, `medical-equipment`, `graphql-explorer`). These are not dashboard-style overview tasks.
- Management is mostly coherent for people, services, queues, patients, scheduling, and All Free requests.
- System mixes settings, finance, security, audit, users, files, notification, Telegram, activation, and phone verification. This is acceptable as a broad bucket but creates duplicates with hidden/contextual settings routes.
- Contextual/no-nav routes are not automatically wrong, but they need documented entry points and active navigation behavior so users do not feel lost.

## Stop Conditions

- This audit did not edit runtime code.
- Findings that require backend/API fixes should be split into later targeted PRs.
- Do not collapse routes or delete aliases without route-registry and user-workflow review.
