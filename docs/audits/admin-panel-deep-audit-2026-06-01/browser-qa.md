# AdminPanel Deep Audit: Browser QA

Date: 2026-06-01
Mode: audit-only

## Environment

- Backend: `http://localhost:18000`
- Frontend: `http://localhost:5173`
- Database: `clinic_dev`
- Health: backend `/api/v1/health` and frontend proxy `/api/v1/health` passed
- Auth: short-lived dev Admin token, no token printed to report
- Viewports:
  - Full route pass: `1280x800`
  - Sample mobile pass: `375x812` for `/admin`, `/admin/services`, `/admin/settings`, `/admin/integrations/telegram`

## Safety Boundaries

Not clicked:

- create
- edit
- delete
- export
- send/test integration actions
- reset/seed/destructive controls

Checked:

- route loads without login redirect
- Admin is not forbidden
- unknown/404 state
- critical API failures
- console errors
- horizontal overflow
- unnamed icon-only buttons
- visible heading/sample content

## Desktop Route Matrix

| Route | Load/auth | API/console result | Heading evidence | Finding |
| --- | --- | --- | --- | --- |
| `/admin` | OK | No failures | KPIs: users, doctors, patients, revenue | OK |
| `/admin/analytics` | OK | No failures | `РђРЅР°Р»РёС‚РёРєР°`, `Р РёС‚Рј РІРёР·РёС‚РѕРІ` | OK; duplicate analytics ownership to review |
| `/admin/webhooks` | OK | No failures | `РЈРїСЂР°РІР»РµРЅРёРµ webhook-Р°РјРё` | OK; grouping questionable |
| `/admin/reports` | OK auth, broken content | `GET /api/v1/reports/daily-summary` -> 500 | `РћС€РёР±РєР° Р·Р°РіСЂСѓР·РєРё РґР°РЅРЅС‹С…` | P0 |
| `/admin/system` | OK | No failures | No clear heading extracted | P3 heading/scanability |
| `/admin/cloud-printing` | OK | No failures | `РћР±Р»Р°С‡РЅР°СЏ РїРµС‡Р°С‚СЊ` | OK |
| `/admin/medical-equipment` | OK | No failures | `РњРµРґРёС†РёРЅСЃРєРѕРµ РѕР±РѕСЂСѓРґРѕРІР°РЅРёРµ` | OK |
| `/admin/graphql-explorer` | OK | React unknown prop warning | `GraphQL API Explorer` | P2 contract warning |
| `/admin/users` | OK | No failures | `РЈРїСЂР°РІР»РµРЅРёРµ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏРјРё` | Duplicate user family |
| `/admin/doctors` | OK | No failures | `РЈРїСЂР°РІР»РµРЅРёРµ РІСЂР°С‡Р°РјРё` | OK |
| `/admin/services` | OK | `MacOSTable` prop warning | `РЎРїСЂР°РІРѕС‡РЅРёРє СѓСЃР»СѓРі` | P2 table contract drift |
| `/admin/queue-cabinet-management` | OK | No failures | `РљР°Р±РёРЅРµС‚С‹ РѕС‡РµСЂРµРґРµР№` | OK |
| `/admin/patients` | OK | No failures | `РЈРїСЂР°РІР»РµРЅРёРµ РїР°С†РёРµРЅС‚Р°РјРё` | OK |
| `/admin/appointments` | OK | No failures | `РЈРїСЂР°РІР»РµРЅРёРµ Р·Р°РїРёСЃСЏРјРё`, empty state | OK |
| `/admin/all-free` | OK | No failures | `Р—Р°СЏРІРєРё All Free` | OK |
| `/admin/clinic-management` | OK | No failures | `РЈРїСЂР°РІР»РµРЅРёРµ РєР»РёРЅРёРєРѕР№` | OK |
| `/admin/ai-settings` | OK | No failures | Generic settings headings | P1 wrong section |
| `/admin/integrations/telegram` | OK | No failures | No `h1/h2/h3` heading extracted | Duplicate Telegram family; heading weak |
| `/admin/notifications` | OK | No failures | `РўРµСЃС‚ Email`, `РўРµСЃС‚ SMS`, `РњР°СЃСЃРѕРІС‹Рµ СЂР°СЃСЃС‹Р»РєРё` | OK; duplicate notification family |
| `/admin/phone-verification` | OK | No failures | `Р’РµСЂРёС„РёРєР°С†РёСЏ С‚РµР»РµС„РѕРЅРѕРІ` | OK |
| `/admin/activation` | OK | No failures | `РЎРёСЃС‚РµРјР° Р°РєС‚РёРІР°С†РёРё` | OK |
| `/admin/finance` | OK | No failures | `Р¤РёРЅР°РЅСЃРѕРІС‹Р№ СѓС‡РµС‚` | OK; grouping questionable |
| `/admin/settings` | OK | No failures | `РќР°СЃС‚СЂРѕР№РєРё` | OK; parallel with `UnifiedSettings` |
| `/admin/security` | OK | No failures | Generic settings headings | P1 wrong section |
| `/admin/audit` | OK | No failures | `РђСѓРґРёС‚` | OK |
| `/admin/advanced-users` | OK | No failures | `РЈРїСЂР°РІР»РµРЅРёРµ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏРјРё` | Duplicate user family |
| `/admin/file-management` | OK auth, API failures | `/api/v1/files/stats` -> 422; `/api/v1/files/` -> 401 | `Р¤Р°Р№Р»РѕРІС‹Р№ РјРµРЅРµРґР¶РµСЂ` | P1 empty-vs-failed ambiguity |
| `/admin/benefit-settings` | OK | No failures | Generic settings headings | P1 wrong section |
| `/admin/wizard-settings` | OK | No failures | Generic settings headings | P1 wrong section |
| `/admin/payment-providers` | OK | No failures | Generic settings headings | P1 wrong section |
| `/admin/clinic-settings` | OK | No failures | Generic settings headings | P1 wrong section |
| `/admin/queue-settings` | OK | No failures | Generic settings headings | P1 wrong section |
| `/admin/telegram-settings` | OK | No failures | `Telegram Bot`, `Р‘С‹СЃС‚СЂС‹Рµ РґРµР№СЃС‚РІРёСЏ` | P1 settings route opens bot tab |
| `/admin/display-settings` | OK | No failures | Generic settings headings | P1 wrong section |
| `/admin/user-select` | OK | No failures | `Р’С‹Р±РѕСЂ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ` | OK |

## Mobile Sample

| Route | Result |
| --- | --- |
| `/admin` | Loads, no horizontal overflow, no unnamed buttons |
| `/admin/services` | Loads, no horizontal overflow, no unnamed buttons, same `MacOSTable` prop warning |
| `/admin/settings` | Loads, no horizontal overflow, no unnamed buttons |
| `/admin/integrations/telegram` | Loads, no horizontal overflow, no unnamed buttons, weak heading extraction |

## Accessibility / Layout Notes

- No unnamed `button` elements were found in the automated pass.
- No document-level horizontal overflow was detected in the tested desktop and sampled mobile routes.
- This pass did not validate keyboard traversal depth or destructive action confirmations because it was audit-only and avoided state-changing actions.

## Blocked / Not Covered

- Full four-viewport matrix was not run for every route because this PR is docs-only and the first pass already identified high-priority functional mismatches.
- Create/edit/delete/export/test actions were not clicked.
- No screenshots were committed.
