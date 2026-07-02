# AdminPanel Deep Audit: Functional Findings

Date: 2026-06-01
Mode: audit-only

## Browser QA Method

Local dev runtime:

- Backend: `http://localhost:18000`
- Frontend: `http://localhost:5173`
- Database: `clinic_dev`
- Auth: short-lived dev Admin token minted with `backend/app/scripts/mint_dev_token.py`
- Safety: no create/edit/delete/test actions were clicked

Browser automation loaded every admin sidebar route plus hidden contextual admin routes at `1280x800`, and sampled `/admin`, `/admin/services`, `/admin/settings`, `/admin/integrations/telegram` at `375x812`.

## P0

### P0-1: `/admin/reports` route fails critical report load

Evidence:

- Route: `/admin/reports`
- Browser heading: `РћС€РёР±РєР° Р·Р°РіСЂСѓР·РєРё РґР°РЅРЅС‹С…`
- Failed API: `GET /api/v1/reports/daily-summary` returned `500`
- Console repeated server errors for the same endpoint

Impact:

Admin reports are a top-level sidebar route. A 500 on the default screen means the route is functionally broken for a core admin reporting workflow.

Likely ownership:

- Frontend surface: `frontend/src/components/admin/UnifiedReports.jsx`
- Backend/API owner: reports endpoint serving `/api/v1/reports/daily-summary`
- Route owner: `admin.reports`

Validation for fix:

- Browser loads `/admin/reports` without error heading.
- Backend targeted test covers empty `clinic_dev`/low-data report summary.
- Frontend handles no-data report state without treating it as a fatal route error.

## P1

### P1-1: Contextual settings routes render generic settings instead of their intended section

Affected routes:

- `/admin/ai-settings`
- `/admin/security`
- `/admin/benefit-settings`
- `/admin/wizard-settings`
- `/admin/payment-providers`
- `/admin/clinic-settings`
- `/admin/queue-settings`
- `/admin/display-settings`

Evidence:

- Browser headings for these direct routes commonly show `Р¦РІРµС‚РѕРІР°СЏ СЃС…РµРјР° РёРЅС‚РµСЂС„РµР№СЃР°`, `РќР°СЃС‚СЂРѕР№РєРё РєР»РёРЅРёРєРё`, `РћСЃРЅРѕРІРЅР°СЏ РёРЅС„РѕСЂРјР°С†РёСЏ`, `РЎРёСЃС‚РµРјРЅС‹Рµ РЅР°СЃС‚СЂРѕР№РєРё`.
- Static root: `AdminPanel` derives `current` from pathname, but `UnifiedSettings` reads only `?section=` and defaults to `general`.

Impact:

Routes look successful but open the wrong functional screen. This is worse than a visible 404 because Admin can silently edit unrelated settings.

Likely ownership:

- `frontend/src/pages/AdminPanel.jsx`
- `frontend/src/components/admin/UnifiedSettings.jsx`
- `frontend/src/routing/routeRegistry.js`

Validation for fix:

- Route contract/browser tests assert direct route -> intended component content:
  - `/admin/security` -> `SecuritySettings`
  - `/admin/ai-settings` -> `AISettings`
  - `/admin/payment-providers` -> `PaymentProviderSettings`
  - `/admin/queue-settings` -> `QueueSettings`
  - `/admin/display-settings` -> `DisplayBoardSettings`
  - `/admin/wizard-settings` -> `WizardSettings`
  - `/admin/benefit-settings` -> `BenefitSettings`

### P1-2: `/admin/telegram-settings` opens Bot Manager, not Telegram settings

Evidence:

- Route: `/admin/telegram-settings`
- Browser headings: `Telegram Bot`, `Р‘С‹СЃС‚СЂС‹Рµ РґРµР№СЃС‚РІРёСЏ`
- Static root: `UnifiedTelegramManagement` defaults `activeTab` to `bot` and does not read pathname or query.

Impact:

The route title/owner says settings, but the first screen is bot operation. For Telegram security/token work this can mislead agents and admins into the wrong surface.

Likely ownership:

- `frontend/src/components/admin/UnifiedTelegramManagement.jsx`
- `frontend/src/pages/AdminPanel.jsx`
- `frontend/src/routing/routeRegistry.js`

### P1-3: File management route loads but protected API calls fail

Evidence:

- Route: `/admin/file-management`
- Failed API responses:
  - `GET /api/v1/files/stats` -> `422`
  - `GET /api/v1/files/` -> `401`
- Browser still shows `Р¤Р°Р№Р»РѕРІС‹Р№ РјРµРЅРµРґР¶РµСЂ` and `Р¤Р°Р№Р»С‹ РЅРµ РЅР°Р№РґРµРЅС‹`.

Impact:

Admin sees an empty file manager that may actually be unauthorized or malformed, not truly empty.

Likely ownership:

- `frontend/src/components/files/FileManager.jsx`
- Backend file endpoints/auth dependencies

### P1-4: Duplicate user-management surfaces can diverge

Evidence:

- `/admin/users` uses `AdminPanel` -> `UnifiedUserManagement`.
- `/admin/advanced-users` uses dedicated `UserManagement`.
- Browser headings for both are `РЈРїСЂР°РІР»РµРЅРёРµ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏРјРё`.

Impact:

Two user admin entry points can drift in permissions, validation, destructive action confirmations, and field coverage.

Recommendation:

Pick one canonical user-management component and make the other route an intentional alias/wrapper with contract tests.

### P1-5: Duplicate Telegram and notification admin surfaces can diverge

Evidence:

- `/admin/integrations/telegram` uses dedicated `TelegramManager`.
- `/admin/telegram-settings` uses `UnifiedTelegramManagement` -> `TelegramBotManager`/`TelegramSettings`.
- `/admin/notifications` uses `EmailSMSManager`.
- `UnifiedNotifications` exists for FCM/Registrar notifications but is not the sidebar route.

Impact:

Integration/security ownership becomes ambiguous. Telegram token/security work is especially sensitive and should not be split across unrelated managers without a clear route map.

## P2

### P2-1: Overview section contains operational/integration tooling

Examples:

- Webhooks
- Reports
- System
- Cloud printing
- Medical equipment
- GraphQL API

Impact:

The Overview group becomes a mixed toolbox instead of a dashboard/monitoring entry. This increases navigation time and makes ownership harder to infer.

### P2-2: AdminPanel is still an oversized route switch and implementation container

Evidence:

- `AdminPanel.jsx` handles local routing, dashboard, patients, doctors, appointments, finance, reports, settings wrappers, services, and feature managers.

Impact:

Small admin fixes have high blast radius. Future fixes should be one route-family per PR and should avoid broad AdminPanel refactors.

### P2-3: Prop warnings indicate component contract drift

Evidence:

- `/admin/services`: `MacOSTable` prop warning, `columns[0].title` object supplied where string expected.
- `/admin/graphql-explorer`: React unknown prop warning.

Impact:

These are not immediate blockers, but they are signs that shared component contracts are drifting.

## P3

### P3-1: Some routes have weak visible headings

Examples:

- `/admin/system` loaded but browser heading extraction found no clear heading.
- `/admin/integrations/telegram` loaded but heading extraction found no `h1/h2/h3` heading.

Impact:

Screen-reader and scanability quality can be improved after functional routing is corrected.

## Stop Conditions

No runtime fixes were attempted. Any fix touching backend report APIs, file auth, route state, or destructive admin actions should be planned as a separate PR with tests.
