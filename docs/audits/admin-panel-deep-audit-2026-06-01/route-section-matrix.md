# AdminPanel Deep Audit: Route / Section Matrix

Date: 2026-06-01
Mode: audit-only, no product runtime changes
Dev runtime: `clinic_dev`, backend `18000`, frontend `5173`

## Scope

Audited the admin route registry, admin route selectors, `AdminPanel` section switch, and browser-rendered admin routes.

Sources inspected:

- `AGENTS.md`
- `.cursorrules`
- `frontend/DESIGN_SYSTEM.md`
- `frontend/THEME_SYSTEM_GUIDE.md`
- `frontend/src/routing/routeRegistry.js`
- `frontend/src/routing/routeSelectors.js`
- `frontend/src/pages/AdminPanel.jsx`
- `frontend/src/components/admin/*`
- `frontend/src/App.jsx`

## Navigation Model

The route registry is the route SSOT. Admin sidebar sections are derived from `routeRegistry.js` through `getAdminNavSections()` and ordered by `routeSelectors.js`.

AdminPanel still derives a local `current` section from either `?section=` or `location.pathname.split('/')[1]`. That means there are two routing concepts in play:

- Registry route: canonical route id, owner, component, nav section.
- AdminPanel local section: pathname segment or query section used by `renderContent()`.

This split is the main source of duplicate or misleading admin screens.

## Matrix

| Route | Registry section | Owner | Registry component | Observed/render path | Audit status |
| --- | --- | --- | --- | --- | --- |
| `/admin` | Overview | `admin.operations` | `AdminPanel` | `renderDashboard()` | OK |
| `/admin/analytics` | Overview | `admin.analytics` | `AnalyticsPage` | Dedicated `AnalyticsPage`; separate from `AdminPanel` analytics case | Review duplicate analytics ownership |
| `/admin/webhooks` | Overview | `admin.integrations` | `AdminPanel` | `WebhookManager` | Loads, but grouping under Overview is questionable |
| `/admin/reports` | Overview | `admin.reports` | `AdminPanel` | `LazyUnifiedReports` | Broken in browser: `/api/v1/reports/daily-summary` returns 500 |
| `/admin/system` | Overview | `admin.system` | `AdminPanel` | `SystemManagement` | Loads with weak heading evidence |
| `/admin/cloud-printing` | Overview | `admin.operations` | `AdminPanel` | `CloudPrintingManager` | Loads |
| `/admin/medical-equipment` | Overview | `admin.operations` | `AdminPanel` | `MedicalEquipmentManager` | Loads |
| `/admin/graphql-explorer` | Overview | `admin.integrations` | `AdminPanel` | `GraphQLExplorer` | Loads; React unknown prop warning |
| `/admin/users` | Management | `admin.users` | `AdminPanel` | `UnifiedUserManagement` | Loads |
| `/admin/doctors` | Management | `admin.users` | `AdminPanel` | `renderDoctors()` | Loads |
| `/admin/services` | Management | `admin.catalog` | `AdminPanel` | `ServiceCatalog` + `QueueProfilesManager` tabs | Loads; MacOSTable prop warning |
| `/admin/queue-cabinet-management` | Management | `admin.queue` | `AdminPanel` | `QueueCabinetManagement` | Loads |
| `/admin/patients` | Management | `admin.patients` | `AdminPanel` | `renderPatients()` | Loads |
| `/admin/appointments` | Management | `admin.scheduling` | `AdminPanel` | `renderAppointments()` | Loads empty state |
| `/admin/all-free` | Management | `admin.operations` | `AdminPanel` | `AllFreeApproval` | Loads |
| `/admin/clinic-management` | System | `admin.operations` | `AdminPanel` | `ClinicManagement` | Loads |
| `/admin/ai-settings` | System | `admin.ai` | `AdminPanel` | `UnifiedSettings` default view | Mismatch: shows generic settings, not AI settings |
| `/admin/integrations/telegram` | System | `admin.integrations` | `TelegramManager` | Dedicated `TelegramManager` | Loads; duplicates Telegram surface family |
| `/admin/notifications` | System | `admin.notifications` | `EmailSMSManager` | Dedicated `EmailSMSManager` | Loads; duplicates notification surface family |
| `/admin/phone-verification` | System | `admin.integrations` | `AdminPanel` | `PhoneVerificationManager` | Loads |
| `/admin/activation` | System | `admin.licensing` | `AdminPanel` | `ActivationSystem` | Loads |
| `/admin/finance` | System | `admin.billing` | `AdminPanel` | `UnifiedFinance` overview | Loads; grouping under System is questionable |
| `/admin/settings` | System | `admin.settings` | `Settings` | Dedicated `Settings` page | Loads; parallel with `UnifiedSettings` |
| `/admin/security` | System | `admin.security` | `AdminPanel` | `UnifiedSettings` default view | Mismatch: shows generic settings, not security |
| `/admin/audit` | System | `admin.audit` | `Audit` | Dedicated `Audit` page | Loads |
| `/admin/advanced-users` | System | `admin.users` | `UserManagement` | Dedicated `UserManagement` | Duplicate family with `/admin/users` |
| `/admin/file-management` | System | `admin.files` | `FileManager` | Dedicated `FileManager` | Loads but API failures 422/401 |
| `/admin/benefit-settings` | Hidden/contextual | `admin.billing` | `AdminPanel` | `UnifiedSettings` default view | Mismatch: benefit settings not selected |
| `/admin/wizard-settings` | Hidden/contextual | `admin.settings` | `AdminPanel` | `UnifiedSettings` default view | Mismatch: wizard settings not selected |
| `/admin/payment-providers` | Hidden/contextual | `admin.billing` | `AdminPanel` | `UnifiedSettings` default view | Mismatch: payment provider settings not selected |
| `/admin/clinic-settings` | Hidden/contextual | `admin.settings` | `AdminPanel` | `UnifiedSettings` default view | Mismatch: direct route does not select clinic-only settings |
| `/admin/queue-settings` | Hidden/contextual | `admin.queue` | `AdminPanel` | `UnifiedSettings` default view | Mismatch: queue settings not selected |
| `/admin/telegram-settings` | Hidden/contextual | `admin.integrations` | `AdminPanel` | `UnifiedTelegramManagement` default bot tab | Mismatch: settings route opens bot manager tab |
| `/admin/display-settings` | Hidden/contextual | `admin.queue` | `AdminPanel` | `UnifiedSettings` default view | Mismatch: display settings not selected |
| `/admin/user-select` | Hidden/contextual | `admin.users` | `UserSelect` | Dedicated `UserSelect` page | Loads |

## Primary Structural Risk

`AdminPanel` passes no explicit section prop to `UnifiedSettings`, `UnifiedFinance`, `UnifiedTelegramManagement`, or similar aggregator components. Some aggregators read `?section=...`, while direct admin routes rely on pathname. The result is that direct contextual routes can load successfully while rendering the wrong functional screen.

## Safe Fix Direction

Do not start by redesigning AdminPanel. The safest first fix slice is route-state alignment:

1. Add a route-section adapter for AdminPanel-owned contextual routes.
2. Pass the derived section explicitly into aggregator components, or make aggregators derive from pathname consistently.
3. Add route contract tests proving each contextual route renders its intended subcomponent.
4. Only then move duplicated route families into clearer navigation groups.
