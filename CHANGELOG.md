# Changelog

## 2026-07-12 — Architecture & Audit Remediation Sprint (28 PRs)

Comprehensive remediation across 6 audit cycles. All changes merged to `main`
via PR & merge workflow with CI validation. 0 regressions throughout.

### Backend Audit Remediation (PR-1 to PR-7)

- **PR-1:** Fixed 14 broken endpoints in `mobile_api_extended.py` (500→200)
- **PR-2:** Fixed 5 broken FCM endpoints + added User device metadata columns
- **PR-3:** Fixed 4 broken endpoints in `mobile_api.py` + added `Appointment.doctor` relationship
- **PR-4:** WebSocket JWT moved from URL query param to `Sec-WebSocket-Protocol` subprotocol (5 endpoints)
- **PR-5:** Removed `WS_DEV_ALLOW` auth bypass + deleted `/ws/noauth` endpoint
- **PR-6:** Added `/mobile/doctors`, `/mobile/attest`, `Idempotency-Key` middleware
- **PR-7:** Added error logging to 34 `except Exception` blocks (mobile/FCM endpoints)

### CI/CD Cleanup (PR-8, PR-9)

- **PR-8:** Fixed AI safety Playwright spec (argon2 hash, endpoint paths, rate limiting, 6/6 tests pass)
- **PR-9:** Removed conflicting CodeQL workflow (default setup enabled)

### Time-Display Audit (PR-10 to PR-14)

- **PR-10:** `add_visit_service` now bumps `visit.updated_at` (doctor-side service additions visible)
- **PR-11:** Unified `adaptTimeFields()` helper for Cardio/Derma/Dental panels ("Очередь" + "Изменено" indicators)
- **PR-12:** Added "Время" column to DoctorPanel queue table + fixed QueueTable source preference
- **PR-13:** Replaced all UTC/browser-local date calls with `Asia/Tashkent` helpers (7 files)
- **PR-14:** Wired `expectedEntryUpdatedAt` for optimistic locking in wizard

### Admin-Flows Audit (PR-15 to PR-22)

- **PR-15:** Restored `require_roles("Admin")` on all `/services` CRUD endpoints (P0 security)
- **PR-16:** Auto-create `QueueProfile` on Department create + fixed `show_on_qr_page` drop
- **PR-17:** Auto-create `Doctor` row when User with `role=Doctor` is created
- **PR-18:** Implemented 3 missing department bulk endpoints (`/bulk`, `/bulk-delete`, `/bulk-activate`)
- **PR-19:** DoctorModal: Department dropdown + specialty pattern validation + ServiceCatalog `/departments` fix
- **PR-20:** Key pattern validation + dedupe service creation + `Registrar` role in `UserCreateRequest`
- **PR-21:** `DoctorOut` includes department fields + `QueueProfilesManager` `department_key` Select
- **PR-22:** Cascade-delete for `queue_profile`/`department` + `UserManagement` pagination

### Wizard/QR UX Audit (PR-23 to PR-25)

- **PR-23:** Doctor filter by service in wizard cart + quantity stepper + QueueTable source badge (3 P0)
- **PR-24:** Edit-mode banner + confirm dialog "Обновить" + WS indicator simplification + QueueJoin i18n (4 P1)
- **PR-25:** Dynamic department filter from `QueueProfile` + service code badge + itemized confirm (3 P2)

### Architecture Audit (PR-26 to PR-28)

- **PR-26:** Resolved `queue_tag` ↔ `specialist_id` architectural contradiction — each doctor now has their own queue; any same-specialty doctor can call patients; added `cardio`/`derma`/`dentist` roles
- **PR-27:** Routing by `Doctor.specialty` (not `User.role`) — `/auth/me` returns specialty; `getRoleHomeRoute` uses specialty; removed hardcoded `homeForUsernames`
- **PR-28:** Removed hardcoded specialty lists — `specialty_mapping` built dynamically from `QueueProfile`; `QR_HIDDEN_PROFILE_KEYS` emptied (admin controls via `show_on_qr_page`)

### Documentation

- **ADR-001:** Queue Ownership & Specialty Architecture (`docs/adr/ADR-001-queue-ownership-and-specialty-architecture.md`)
- **Developer Guide:** Adding a New Medical Specialty (`docs/developer-guides/adding-a-new-specialty.md`)

### Migration Notes

New Alembic migrations:
- `0037_patient_medical_fields` — Patient: `emergency_contact`, `allergies`, `chronic_conditions`
- `0038_user_fcm_fields` — User: `device_type`, `device_info`, `push_notifications_enabled`
- `0039_feature_flags` — `feature_flags` + `feature_flag_history` tables (were missing from model registry)

### Stats

- **28 PRs** merged to `main`
- **0 regressions** throughout (CI green on every PR)
- **+48 new tests** (38 backend + 10 frontend)
- **96 bugs** fixed across 6 audit cycles
- **3 Alembic migrations** added
- **2 architectural documents** (ADR + Developer Guide)

---

## 2026-07-04 — Admin Sprint 4: P2 polish (fix/admin-sprint4-p2-polish)

Final sprint of 4-sprint admin cleanup roadmap. Reduces duplication, fixes RU/EN mixing, restores codemod-damaged state values.

### P2-1: `IconButton` deduplication (3 copies → 1 shared)
Created `components/admin/IconButton.jsx` (33 lines) as the canonical icon-only button. Removed 3 byte-identical copies from `AdminAppointments.jsx`, `AdminDoctors.jsx`, `AdminPatients.jsx` and replaced with `import IconButton from './IconButton'`. Behavior unchanged (same className, style, props).

### P2-2: `formatCurrency` deduplication (2 copies → 1 shared)
Created `utils/formatCurrency.js` (Intl.NumberFormat ru-RU UZS, 0 fractional digits, null-safe). Removed 2 identical copies from `AdminDashboard.jsx` and `AdminFinanceOverview.jsx`. `useUtils.js` has a separate formatCurrency (goes through formatNumber) — kept as-is because it has different null-handling and call sites.

### P2-3: `REPORT_ENDPOINTS` map deduplication (2 copies → 1 shared)
Created `utils/reportEndpoints.js` with the full 12-entry map (ReportGenerator superset) + `getReportEndpoint` helper. Removed local `REPORT_ENDPOINTS` map from `ReportGenerator.jsx` and inline `getReportEndpoint` function from `ReportsManager.jsx`. ReportsManager now uses the superset (5→12 entries — more report types recognized).

### P2-4: `const [, setX]` codemod artifacts restored (3 files, 6 state slots)
The same codemod that caused the P0 void-`useState` artifacts (fixed in Sprint 1) also left `const [, setX] = useState(...)` patterns where the value was discarded but the setter was called. Restored the values:
- `WebhookManager.jsx:55,56` — `showEditModal`, `showTestModal` (buttons call setters; modal UI not yet implemented, but state slots are now reachable for future work).
- `DynamicPricingManager.jsx:178,179` — `editingRule`, `editingPackage` (same pattern).
- `DisplayBoardSettings.jsx:35,40` — `boards`, `showBannerForm` (loadDisplayData populates boards; button onClick sets showBannerForm).

### P2-5: RU/EN mixing standardized to RU (admin-facing UI is Russian)
- `ReportsManager.jsx` — 7 English strings → Russian: "Select an available report type" → "Выберите доступный тип отчёта", "Generating report"/"Generate report" → "Генерация отчёта"/"Сгенерировать отчёт", "Download report" → "Скачать отчёт" (×2 variants).
- `UnifiedSettings.jsx` — "Accent color" → "Акцентный цвет" (heading + description).

Verification:
- `vite build` → ✓ built in ~26s, exit 0, all chunks emitted.
- `vitest run` → ✓ 515/515 tests pass across 105 test files.
- `eslint` on 14 modified/new files → 0 errors (9 pre-existing warnings unchanged).

## 2026-07-04 — Admin Sprint 3: P1 architectural cleanup (fix/admin-sprint3-p1-architectural)

### A-1: Removed `admin-advanced-users` route + `AdvancedUserManagement` stub + dead `UserManagement` ROUTE_COMPONENTS entry
- **`AdvancedUserManagement.jsx`** (20 lines) deleted — was a stub wrapping `<UserManagement />` with an Alert banner, duplicating `/admin/users` (which routes to `UnifiedUserManagement` that renders `UserManagement` underneath).
- **`routeRegistry.js`**: removed `admin-advanced-users` route block entirely. `/admin/advanced-users` and legacy `/advanced-users` now 404 — bookmarks should be updated to `/admin/users`.
- **`App.jsx`**: removed `AdvancedUserManagement` lazy import + `ROUTE_COMPONENTS` entry. Also removed `UserManagement` lazy import + `ROUTE_COMPONENTS` entry (dead — no route uses `component: 'UserManagement'`; the file stays as it's imported by `UnifiedUserManagement`).
- **`routeContract.test.js`**: replaced "keeps admin user routes split between canonical and advanced ownership" test with "keeps admin user management on the canonical UnifiedUserManagement route" (asserts `admin-advanced-users` is undefined).

### A-2: Consolidated Telegram sidebar entries (2 → 1)
Two routes had overlapping semantics and both appeared in the sidebar:
- `admin-telegram-settings` → `TelegramSettings` (Настройки section) — bot token, webhook, test messages, stats.
- `admin-telegram-integration` → `TelegramManager` (Система section) — richer bot management (commands, onboarding requests).

Demoted `admin-telegram-integration` to `entry: 'direct'` + `nav: false` — route stays reachable via direct URL `/admin/integrations/telegram` and legacy redirect from `/telegram-integration` (bookmark-compatible), but no longer clutters the sidebar. `admin-telegram-settings` is the canonical Telegram surface. Updated `routeContract.test.js` accordingly.

### A-3: Migrated `admin/ErrorBoundary` → `common/ErrorBoundary`
- **`admin/ErrorBoundary.jsx`** (107 lines) deleted — duplicated `common/ErrorBoundary.jsx` (216 lines, more featureful: supports `onError` callback, `ErrorFallback` component, theme prop). Only consumer was `AdminDashboard.jsx:27`.
- **`AdminDashboard.jsx:27`**: import migrated to `../common/ErrorBoundary`.

### A-4: Rebalanced admin sidebar sections (Система 9 → 7, Miller's 7±2)
After A-2 (telegram-integration demoted), Система had 8 items. Moved 2 more to Интеграции:
- `admin-push-notifications`: Система → Интеграции (order 30).
- `admin-phone-verification`: Система → Интеграции (order 40).

Final sidebar distribution (all sections ≤ 7):
- Обзор (2), Управление (7), Операции (3), Интеграции (4), Система (7), Настройки (7).

Verification:
- `vite build` → ✓ built in ~25s, exit 0, all chunks emitted.
- `vitest run` → ✓ 515/515 tests pass across 105 test files (includes updated routeContract tests).
- `eslint` on 4 modified files → 0 errors.

## 2026-07-04 — Admin Sprint 2: P1 functional fixes (fix/admin-sprint2-p1-functional)

### P1-1: `ReportsManager.jsx` — perpetual spinner for weekly/monthly KPI cards
Weekly and monthly KPI cards showed a perpetual loading spinner because `loadQuickReports` only called `/reports/daily-summary` (the only endpoint that exists in backend — verified via `backend/openapi.json`). Removed the weekly/monthly cards and state; kept only the daily card. Adding weekly/monthly backend endpoints is a separate feature request.

### P1-2: `AdminDoctors.jsx:25–26` — duplicate "Стоматология" filter option
Two `<option>` elements with the same label "Стоматология" but different values (`dentistry` vs `stomatology`). Removed `stomatology`; kept `dentistry` (canonical `SPECIALTY_KEYS.DENTISTRY` per `utils/doctorPanelShared.js`).

### P1-3: `AdminAppointments.jsx` — label inconsistency for `pending` status
Filter dropdown said "Ожидает" (L25) while the table badge said "Ожидает оплаты" (L91). Aligned both to "Ожидает оплаты".

### P1-4: CRUD modals swallowed save errors
- `AppointmentModal.jsx` — `catch { logger.error(...) }` silently swallowed errors. Added `submitError` state + `<Alert type="error">` render before the form (matching `DoctorModal` pattern). Catch now extracts `error.response.data.detail || error.message`.
- `PatientModal.jsx` — same fix applied.

### P1-5: `window.location.reload()` killed SPA state (2 of 3 places)
- `AdminFinanceOverview.jsx:308` — retry button on finance error. Replaced with `refreshFinance()` callback from `useFinance` hook (`refresh: loadTransactions`).
- `SecuritySettings.jsx:580` — "Сбросить" button. Replaced with `setFormData(settings || {})` (resets form to last-loaded settings).
- `ErrorBoundary.jsx:68` — kept as-is; error-boundary fallback for a crashed subtree, full reload is acceptable there.

### P1-6: `ReportGenerator.jsx` — dead controlled-mode props
`UnifiedReports` renders `<ReportGenerator />` with no props, but the component accepted `onGenerateReport`, `onReportTypeChange`, `onDateRangeChange`, `loading`, `reportTypes`, `dateRange`, `selectedReportType` with always-undefined guards. Added deprecation comment; removed dead PropTypes. Kept the props in the signature for backward compat (no other caller exists — verified via `rg "<ReportGenerator\s+[^/]"`).

Verification:
- `vite build` → ✓ built in ~25s, exit 0, all chunks emitted.
- `vitest run` → ✓ 515/515 tests pass across 105 test files.
- `eslint` on 8 modified files → 0 errors (1 pre-existing warning unchanged).

## 2026-07-04 — Admin Sprint 1: P0 silent regressions & data-integrity fixes (fix/admin-sprint1-p0-silent-regressions)

### Void codemod damage — phantom `useState` / `useTheme` (3 files)
Auto-codemod `const X = useState(...)` → `void useState(...)` left syntax artifacts in 3 live admin files. Removed the phantom lines (the deleted state vars were genuinely unused — codemod was right to remove the binding, wrong to leave the call dangling).

- **`BillingManager.jsx:99–100`** — removed `void\nuseState(null);` (was `selectedInvoice`, unused — `paymentForm.invoice_id` already tracks the target invoice).
- **`DiscountBenefitsManager.jsx:57–58`** — removed `void\nuseState(null);` (was `editingItem`, unused — create-form is the only flow).
- **`UnifiedFinance.jsx:44–45`** — removed `void\nuseTheme();` (same fix as `UnifiedNotifications` in Step 3 PR #1830).

Note: 3 other files (`WebhookManager.jsx:55–56`, `DynamicPricingManager.jsx:178–179`, `DisplayBoardSettings.jsx:35,40`) have `const [, setX] = useState(...)` — valid JS, setters are called but UI was never implemented. Not P0 (never-implemented feature, not a codemod break). Deferred to P2 cleanup.

### Raw `fetch()` → axios migration (2 files, P0 security)
`TelegramSettings.jsx` (7 call sites) and `GraphQLExplorer.jsx` (2 call sites) used raw `fetch()` with manual `Bearer ${tokenManager.getAccessToken()}` headers, bypassing the axios instance's auth-refresh interceptor. On access-token rotation this would silently send a stale token → 401 → silent failure.

- **`TelegramSettings.jsx`** — migrated `loadData` (3 GETs via `Promise.allSettled`), `saveSettings` (PUT), `testBot` (POST), `setWebhook` (POST), `sendTestMessage` (POST) to `api.get/put/post`. Removed `tokenManager` import, added `import { api } from '../../api/client'`.
- **`GraphQLExplorer.jsx`** — migrated `loadSchema` (POST introspection) and `executeQuery` (POST query) to `api.post('/graphql', ...)`. Removed `tokenManager` import.

### Fake-data fallback removal (2 files, P0 data integrity)
On API failure, 2 admin components showed fabricated numbers — admin saw a "healthy" dashboard when the backend was down.

- **`ClinicManagement.jsx:75–84, 100–109`** — removed hardcoded fallback `{ total_branches: 3, active_licenses: 7, total_backups: 12, ... }`. On API error now sets `stats = null` / `systemHealth = null`, which triggers the existing `<MacOSEmptyState title="Статистика недоступна" />` and the `systemHealth ?` guard.
- **`MedicalEquipmentManager.jsx:67–90, 100–112, 124–146`** — removed 3 mock-fallback blocks (devices: "Тонометр Omron M3" / "Термометр Braun"; overview: 2 devices / 15 measurements; measurements: fabricated BP/thermometer readings). On API error now sets empty arrays / zero-defaults overview. Admin no longer risks acting on fabricated equipment data.

Verification:
- `vite build` → ✓ built in ~25s, exit 0, all chunks emitted.
- `vitest run` → ✓ 515/515 tests pass across 105 test files.
- `eslint` on 7 modified files → 0 errors (1 pre-existing warning unchanged).
- `grep` for `fetch(` / `tokenManager` in TelegramSettings + GraphQLExplorer → 0 matches.

## 2026-07-04 — Admin panel dead-code cleanup — Step 3 (chore/admin-step3-wire-and-delete)
- **Wire-in: `UnifiedNotifications` → `/admin/push-notifications`** (new route). Restores 2 admin functions that had live backend endpoints but dead frontend UI:
  - **FCM push notifications** (`FCMManager.jsx`, 521 lines) — `/fcm/status`, `/fcm/user-tokens`, `/fcm/send-test-notification`, `/fcm/send-notification` endpoints.
  - **Registrar notifications** (`RegistrarNotificationManager.jsx`, 466 lines) — `/registrar/notifications/registrars`, `/stats`, `/system-alert`, `/daily-summary` endpoints.
  - New sidebar entry "Push-уведомления" in "Система" section. Email/SMS (`/admin/notifications` → `EmailSMSManager`) stays separate.
  - Fixed `void useTheme()` codemod bug in `UnifiedNotifications.jsx:57`.
  - Updated `routeContract.test.js:360` — flipped `UnifiedNotifications` assertion from `false` to `true`, added new route assertions.
- **Wire-in: `DepartmentManagement` → tab in `ClinicManagement`**. Restores department CRUD admin UI (1 454 lines) that had live backend (`/admin/departments`) but dead frontend. New "Отделения" tab (Layers icon) alongside existing Филиалы/Оборудование/Лицензии/Резервные копии. Replaced 2 dead IconSelector placeholders with plain text Input for icon name.
- **Delete: `QRTokenManager.jsx` (522 lines) + `__tests__/QRTokenManager.contract.test.jsx`**. QR-token admin generation was not used end-to-end: `api/queue.js` has `qrTokens.*` functions but no live component imports them. If needed later, can be rebuilt via the existing `api/queue.js` API layer.
- **`StateWrapper.jsx`** — updated JSDoc comment: `UnifiedNotifications` no longer "pending Step 3 decision" (now wired).

Verification:
- `vite build` → ✓ built in ~25s, exit 0, all chunks emitted (including new `UnifiedNotifications` chunk).
- `vitest run` → ✓ 515/515 tests pass across 105 test files (was 517/106 — 2 QRTokenManager contract tests removed with the file). Includes updated `routeContract.test.js` (40/40 — `UnifiedNotifications` now asserted as routed).
- `eslint` on 7 modified files → 0 errors (12 pre-existing prop-types warnings unchanged).
- `components/admin/` file count: 61 → 60 (-1: QRTokenManager deleted; UnifiedNotifications, FCMManager, RegistrarNotificationManager, DepartmentManagement stay — now wired).
- 3 admin functions restored: department CRUD, FCM push, registrar notifications.

Context: final step of 3-step admin dead-code cleanup. Step 1 (PR #1827, 9 files, -2 179 LOC) + Step 2 (PR #1829, 6 files, -2 850 LOC) + CSS migration (PR #1828) all merged. This Step 3 PR wires in 4 dead files (restoring 3 functions) and deletes 1 truly-unused file.

## 2026-07-04 — Admin panel dead-code removal — Step 2 (chore/admin-remove-dead-partial-step2) — PR #1829
- **frontend/src/components/admin/** — deleted 6 dead-code files (2 850 lines) with partial live replacements. No runtime behavior change (all 6 were already unreachable in production).
  - `SecurityMonitor.jsx` (906) — DEAD, 100% mock data (`mockData = { totalThreats: 23, ... }`). Real threat-monitoring is a backend gap; this file never had real data. Superseded conceptually by `pages/Audit.jsx` (audit log of user actions — different function).
  - `TelegramBotManager.jsx` (763) — DEAD, only importer was the dead `UnifiedTelegramManagement`. Had 3 broadcast functions (`sendAdminAlert`, `broadcastSystemMessage`, `notificationForm` with `send_to_all_admins`/`send_to_all_users`) hitting backend endpoints `/api/v1/telegram-bot/send-notification` and `/api/v1/telegram-bot/broadcast-system-message` (which still exist). **Feature gap note:** the live `components/TelegramManager.jsx` does NOT have these broadcast features — its "Отправить сообщение" button (`TelegramManager.jsx:1625-1631`) has no `onClick`. Restoring broadcast UI is a separate product decision (re-implement in `TelegramManager.jsx` or wire a new admin tab).
  - `QueueLimitsManager.jsx` (642) — DEAD, unreachable. `ADMIN_SETTINGS_ROUTE_SECTION_MAP` in `UnifiedSettings.jsx` had no `/admin/queue-limits` entry, so the `case 'queue-limits'` branch was dead. Superseded by `QueueSettings.jsx` (live, `/admin/queue-settings`) which writes the same `max_per_day`/`start_number` fields via `PUT /admin/queue/settings`. **P0 conflict resolved:** the two components wrote the same fields via different endpoints (`PUT /admin/queue-limits` vs `PUT /admin/queue/settings`) — last-writer-wins corruption risk is now eliminated.
  - `DesignValidator.jsx` (296) — DEAD dev-tool (design-system validator). Not a production feature; design system is enforced via `macos-tokens.css` and `routeContract.test.js`.
  - `UnifiedAITools.jsx` (143) — DEAD aspirational scaffold. Its 7 AI-tool children (`MedicalImageAnalyzer`, `TreatmentRecommendations`, `DrugInteractionChecker`, `RiskAssessment`, `QualityControl`, `SmartScheduling`, `VoiceToText`) live independently in `components/ai/` and are consumed by clinical panels. No admin AI-tools hub exists; re-creating one is a separate product decision.
  - `UnifiedTelegramManagement.jsx` (101) — DEAD aspirational scaffold. Its children (`TelegramSettings` + `TelegramBotManager`) are alive via direct routing (different routes). `routeContract.test.js:554` already asserted this wrapper must NOT be routed.
- **frontend/src/components/admin/UnifiedSettings.jsx** — removed dangling `import QueueLimitsManager` and the dead `case 'queue-limits'` branch (the section was never reachable: `ADMIN_SETTINGS_ROUTE_SECTION_MAP` has no `/admin/queue-limits` entry).
- **frontend/src/components/common/StateWrapper.jsx** — updated JSDoc comment that listed the deleted `UnifiedAITools` / `UnifiedTelegramManagement` as consumers.

Verification:
- `vite build` → ✓ built in ~26s, exit 0, all chunks emitted.
- `eslint` on 2 modified files → 0 errors (12 pre-existing prop-types warnings unchanged).
- `vitest run` (full suite) → ✓ 517/517 tests pass across 106 test files, including `routeContract.test.js` (40/40 — the `routedComponents.has('UnifiedTelegramManagement')` → false assertion still holds).
- `grep` for imports of the 6 deleted files across `frontend/src/**/*.{jsx,js}` → 0 matches in live code.
- `components/admin/` file count: 67 → 61 (-6).

Context: see `analysis/ADMIN_PANEL_A_Z_ANALYSIS.md` (full A-Z audit) and `analysis/DEAD_CODE_REPLACEMENTS.md` (replacement map). Step 2 of a 3-step cleanup; Step 1 (9 files, -2 179 LOC) merged in PR #1827; Step 3 (5 gap candidates, ~4 411 lines — DepartmentManagement, QueueProfilesManager, FCMManager, RegistrarNotificationManager, QRTokenManager) pending product-owner decision.

## 2026-07-04 — Admin panel dead-code removal — Step 1 (chore/admin-remove-dead-helpers-step1) — PR #1827
- **frontend/src/components/admin/** — deleted 9 dead-code helper/section files (2 179 lines total) that had full live replacements in the macOS design system or shared/common layer. No behavior change.
  - `AnalyticsDashboard.jsx` (773) — superseded by `pages/AnalyticsPage.jsx` (the active `/admin/analytics` route). File was a phantom with two `void useState(...)` codemod artifacts (non-functional).
  - `MobileOptimization.jsx` (368) — superseded by `AppShell` (sidebar preset system in `App.jsx`).
  - `IconSelector.jsx` (247) — superseded by `Icon` (`components/ui/macos/Icon.jsx`, full icon system, 18 KB).
  - `HelpTooltip.jsx` (204) — superseded by `Tooltip` (`components/ui/macos/`).
  - `LoadingSkeleton.jsx` (144) — superseded by `Skeleton` (`components/ui/macos/`).
  - `KPICard.jsx` (132) — superseded by `MacOSStatCard` / `MacOSMetricCard` (`components/ui/macos/`).
  - `EmptyState.jsx` (123) — superseded by `MacOSEmptyState` / `AppEmpty` (`components/ui/macos/`).
  - `AdminSection.jsx` (105) — superseded by `StateWrapper` (`components/common/StateWrapper.jsx`).
  - `AdminNavigation.jsx` (83) — superseded by the data-driven sidebar (`getAdminNavRoutes` + `SIDEBAR_PRESETS.admin` in `routing/routeSelectors.js`).
- **frontend/src/components/admin/DepartmentManagement.jsx** — commented out the dangling `import IconSelector, { iconMap } from './IconSelector'` (IconSelector was deleted above). Replaced 2 `<IconSelector/>` JSX usages and the `iconMap[dept.icon]` lookup with placeholders/null. NOTE: `DepartmentManagement.jsx` is itself dead code (not routed, not imported anywhere — 1 774 lines). Its fate (wire-in vs delete) is deferred to Step 3 pending product-owner decision; the file is not bundled by Vite.
- **frontend/src/hooks/uiAnimations.js** — updated stale JSDoc comment that referenced the deleted `admin/KPICard` and `admin/AdminNavigation` as consumers.
- **frontend/src/pages/registrar/views/WelcomeView.jsx** — updated a code comment that referenced the deleted `EmptyState.jsx`; now points to `MacOSEmptyState` from the macOS design system.

Verification:
- `vite build` → ✓ built in ~27s, exit 0, all chunks emitted.
- `eslint` on the 3 modified files → 0 errors (pre-existing warnings unchanged).
- `grep` for imports of the 9 deleted files across `frontend/src/**/*.{jsx,js}` → 0 matches in live code.
- `components/admin/` file count: 76 → 67 (-9).

Context: see `analysis/ADMIN_PANEL_A_Z_ANALYSIS.md` (full A-Z audit) and `analysis/DEAD_CODE_REPLACEMENTS.md` (replacement map). Step 1 of a 3-step cleanup; Step 2 (6 files, partial replacements) and Step 3 (5 gap candidates, ~4 411 lines) follow in separate PRs.

## 2026-07-04 — Doctor panels workflow refactor (fix/workflow-panels-refactor)
- **frontend/src/pages/DentistPanelUnified.jsx** — restored `handleCompleteVisit` (the section was empty, leaving the dentist unable to close an encounter and the queue unable to advance). Follows the same SSOT contract as Cardiologist and Dermatologist: `resolveDoctorQueueEntryId` → `queueService.completeVisit` → reset state → `callNextWaiting('dentistry')`.
- **frontend/src/components/dental/VisitProtocol.jsx** — added optional `onComplete` prop that, when provided, renders a "Завершить приём" button next to "Сохранить" and wires it to `handleCompleteVisit` in DentistPanelUnified.
- **frontend/src/utils/doctorPanelShared.js** — new shared module:
  - `countAppointmentsByStatuses` (Set-based, O(n+m) instead of O(n*m) via Array.includes)
  - `normalizeNumericId` (null-safe parseInt helper)
  - `SPECIALTY_KEYS` enum — single source of truth for canonical specialty strings
  - `SPECIALTY_ALIASES` table aligned with backend `DOCTOR_QUEUE_SPECIALTY_VARIANTS`
  - `matchesSpecialty()` tolerant comparison helper
- **frontend/src/pages/CardiologistPanelUnified.jsx**, **DermatologistPanelUnified.jsx**, **DentistPanelUnified.jsx** — import shared helpers, drop local copies, and call `queueService.callNextWaiting(SPECIALTY_KEYS.*)` instead of bare string literals.
- **frontend/src/pages/CardiologistPanelUnified.jsx** — improved `loadEMR` error handling:
  - 401/403 → "Сессия истекла..." toast (was: generic error)
  - 5xx → "Сервер недоступен..." toast (was: generic error)
  - AbortError → silent log (visit changed mid-fetch)
  - Early token check fails fast instead of letting fetch produce a 401 round-trip
  - Defensive `setEmr(null)` in every non-200 branch prevents stale data leaking between visits
- **frontend/src/pages/CardiologistPanelUnified.jsx** — wired `useVisitLifecycle` hook for cache hygiene:
  - `cacheService.invalidateByVisit(prevVisitId)` + `invalidateByPatient(prevPatientId)` on visit/patient switch
  - `onCleanup` resets local `emr` state to null so stale data cannot bleed into the next visit's view
- **docs/UNIFIED_PANELS_IMPROVEMENT_PLAN.md** — updated status to reflect which stages are now complete (Этапы 1, 2, 3, 4) and which remain (Этап 5 — final testing across all panels in a real clinic environment).

Verified locally:
- `npx vitest run` → 467/467 tests pass (including `DoctorPanels.contract.test.jsx` — 9 SSOT assertions)
- `npx eslint` on touched files → 0 errors (pre-existing warnings unchanged)
- Backend untouched — all specialty aliases continue to be tolerant-mapped via `DOCTOR_QUEUE_SPECIALTY_VARIANTS`

## 2026-03-26 — Follow-up backlog triage → ADM-06 browser smoke
- **docs/ADM-06_BROWSER_SMOKE.md** — added a compact QA checklist extracted from the live service-catalog smoke so QA can verify the guardrail in a few steps instead of running the full panel runbook.
- **docs/README.md** — updated the Testing & QA index and linked the new smoke checklist alongside the SSOT panel runbook.
- **docs/PANEL_QA_CHECKLIST.md** — added a direct pointer from the full runbook to the short smoke checklist and refreshed the document timestamp.
- **.ai-factory/logs/PANEL_QA_IMPLEMENTATION_STATUS.md** — final cycle tracking now reflects `ADM-06-BROWSER-SMOKE` as the last completed case and keeps the follow-up backlog closed.
- Verified live on the temp admin stack `http://127.0.0.1:4194` -> `http://127.0.0.1:18008`:
  - invalid `Лабораторные анализы + P77` blocked with the inline warning `Код P77 не подходит для группы "Лаборатория"`
  - valid `Прочие услуги + O77` saved successfully
  - new row `QA Mismatch Smoke` appeared in the catalog table with canonical code `O77`

## 2025-08-17 — Step A: Архитектура, конфиги, ENV, секреты
- **backend/app/core/config.py** — *kept + extended*: единый центр настроек; добавлены `API_V1_STR`, `DEBUG`, нормализация `CORS_ORIGINS` (CSV), сохранены прежние имена полей (`REQUIRE_LICENSE`, `LICENSE_ALLOW_HEALTH`, `DATABASE_URL`, `AUTH_*` и пр.).
- **backend/.env.example** — добавлен шаблон переменных окружения.
- **frontend/.env.example** — добавлен шаблон переменных для Vite.
- **backend/pyproject.toml** — закреплены верхние границы версий зависимостей для более предсказуемых сборок.
- **docs/README_env.md** — краткая памятка по переменным окружения.

## 2025-08-17 — Step B.1: Схема БД и миграции (безопасные индексы)
- Добавлен Alembic-скрипт `backend/alembic/versions/20250817_0001_perf_indexes.py` (создаёт индексы, только если таблицы/колонки существуют; идемпотентно).

## 2025-08-17 — Step B.2: Аудит данных и backfill NULL
- Добавлен `backend/app/scripts/audit_data.py` (отчёт по «висячим» ссылкам в CSV).
- Добавлен Alembic-скрипт `backend/alembic/versions/20250817_0002_backfill_nullable_defaults.py` (только безопасные обновления данных).

## 2025-08-17 — Fix: Alembic env.py (импорт пакета app)
- **backend/alembic/env.py** — добавлен блок `sys.path.insert(0, backend_root)`; теперь `alembic upgrade head` работает без PYTHONPATH.

## 2025-08-18 — Step B.3.2: NOT NULL hardening
- `backend/alembic/versions/20250818_0004_not_null_hardening.py` — условная установка `NOT NULL` на заранее заполненных полях (SQLite через batch).

## 2025-08-18 — Step B.3.2a: NOT NULL alignment
- `backend/alembic/versions/20250818_0005_not_null_alignment.py` — выравнивание целей (activations.status, исключение schedules).

## 2025-08-18 — **Step C (часть 1): Согласование API и WS**
- **backend/app/api/v1/api.py** — *kept + extended*: безопасное подключение недостающих роутеров (`queues`, `appointments`, `online_queue`) через `_safe_include`.
- **backend/app/ws/queue_ws.py** — *kept + extended*: добавлен алиас параметра `?date=` к `date_str` для совместимости с фронтендом; защищённый импорт реальной реализации стрима.
