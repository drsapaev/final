# AdminPanel Deep Audit: Duplicate Function Families

Date: 2026-06-01
Mode: audit-only

## Why This Matters

AdminPanel currently contains both route-level components and internal aggregator components. Some routes are canonical screens; others are hidden/contextual routes that load the same aggregator but do not select the intended sub-screen. This creates duplicate or misleading functions.

## Duplicate / Ambiguous Families

| Family | Routes / components | Risk | Recommended owner decision |
| --- | --- | --- | --- |
| User management | `/admin/users` -> `UnifiedUserManagement`; `/admin/advanced-users` -> `UserManagement` | Two screens can diverge on RBAC, destructive confirmations, export/transfer flows | Make one canonical; turn the other into a documented advanced tab or route alias |
| Settings | `/admin/settings` -> `Settings`; many AdminPanel routes -> `UnifiedSettings` | Generic settings and route-specific settings are split; direct contextual routes often show wrong content | Define `Settings` vs `UnifiedSettings` boundary or consolidate behind route-aware adapter |
| Security | `/admin/security` -> `UnifiedSettings` default, while `SecuritySettings` and `SecurityMonitor` exist | Security route can silently show generic settings instead of security controls | Make `/admin/security` explicitly render `SecuritySettings`/security surface |
| Billing/benefits/providers | `/admin/finance`; hidden `/admin/benefit-settings`; hidden `/admin/payment-providers`; `UnifiedFinance`; `UnifiedSettings`; `DiscountBenefitsManager`; `PaymentProviderSettings` | Billing functions split between finance tabs and generic settings routes | Billing/payment provider routes should be owned by finance/billing or explicit settings subroutes, not default generic settings |
| Queue settings/display | `/admin/queue-cabinet-management`; hidden `/admin/queue-settings`; hidden `/admin/display-settings`; `QueueSettings`; `DisplayBoardSettings`; `QueueProfilesManager` | Queue operations, queue profiles, and display settings are adjacent but route behavior is inconsistent | Keep queue cabinets/profiles separate from queue/display settings and test each route |
| Telegram | `/admin/integrations/telegram` -> `TelegramManager`; hidden `/admin/telegram-settings` -> `UnifiedTelegramManagement`; `TelegramBotManager`; `TelegramSettings` | Token/security/storage/webhook work can land in the wrong component | Treat `/admin/integrations/telegram` as canonical operational Telegram manager unless a settings route is explicitly scoped |
| Notifications | `/admin/notifications` -> `EmailSMSManager`; `UnifiedNotifications` -> `FCMManager`/`RegistrarNotificationManager` | Email/SMS/FCM/registrar notification settings can split and drift | Create a notification route map by channel and user-facing policy |
| Analytics | `/admin/analytics` -> `AnalyticsPage`; `AdminPanel` has `case 'analytics'` -> `AnalyticsDashboard` | Same semantic route name has a dedicated route and an internal AdminPanel case | Remove/demote unreachable duplicate or document intentional split |
| Services/departments | `/admin/services` -> service catalog + queue profiles; `case 'departments'` -> queue profiles deprecated redirect; `DepartmentManagement` still exists | Legacy department model can confuse queue profile/service catalog ownership | Keep service catalog as SSOT; document or retire legacy department UI separately |

## Findings

### D1: Contextual routes load default aggregator content

The most urgent duplicate-function problem is not just duplication; it is false success. Several hidden routes successfully render a page but do not select the intended subcomponent.

Examples:

- `/admin/payment-providers` should show provider settings, but browser headings show generic settings/clinic content.
- `/admin/queue-settings` should show queue settings, but browser headings show generic settings/clinic content.
- `/admin/display-settings` should show display board settings, but browser headings show generic settings/clinic content.

### D2: Dedicated route components and AdminPanel wrappers coexist

`App.jsx` registers dedicated components for `AnalyticsPage`, `Settings`, `TelegramManager`, `EmailSMSManager`, `FileManager`, `Audit`, and `UserManagement`, while `AdminPanel` also contains wrappers for similar concepts. This is not automatically wrong, but each pair needs an explicit boundary.

### D3: Aggregator tabs are not consistently route-aware

`UnifiedFinance` and `UnifiedNotifications` read `?section=...`; `UnifiedTelegramManagement` defaults to bot tab; `UnifiedSettings` reads query only. Direct pathname routes do not automatically become query sections.

## Recommended Slices

1. Route-state adapter slice:
   - Make AdminPanel pass an explicit `section` to aggregators based on canonical route id/path.
   - Add route contract tests for hidden contextual routes.

2. Settings/security slice:
   - Fix `/admin/security`, `/admin/ai-settings`, `/admin/payment-providers`, `/admin/queue-settings`, `/admin/display-settings`, `/admin/wizard-settings`, `/admin/benefit-settings`.

3. Telegram/notifications route map slice:
   - Decide canonical Telegram operational route vs settings route.
   - Decide notification channel route map.

4. User management consolidation slice:
   - Make `/admin/users` and `/admin/advanced-users` intentional, tested entry points.

5. Legacy services/departments slice:
   - Document or remove the stale `departments`/`DepartmentManagement` path in a later PR.
