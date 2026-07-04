# Changelog

## 2026-07-04 — Admin panel dead-code removal — Step 2 (chore/admin-remove-dead-partial-step2)
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
