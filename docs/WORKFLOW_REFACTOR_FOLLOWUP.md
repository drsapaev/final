# Workflow Refactor — Follow-up Audit & Manual Testing Plan

**Связанные документы:**
- `CHANGELOG.md` — запись 2026-07-04
- `docs/UNIFIED_PANELS_IMPROVEMENT_PLAN.md` — исходный план унификации панелей
- PR #1779 (merged, commit `c77aa2b`)

**Цель этого документа:** зафиксировать, что осталось после cloud-фазы рефакторинга, какие задачи требуют запуска проекта локально, какие проблемы ещё существуют и в каком направлении делать следующий аудит.

---

## Часть 1. Задачи, требующие локального запуска проекта

Эти задачи нельзя выполнить облачно — нужна локальная установка backend + frontend + БД, либо доступ к staging/production контуру.

### 1.1. Per-panel E2E клинический флоу

Для каждой из трёх doctor-панелей проверить полный цикл приёма пациента:

#### Cardiologist (`/doctor/cardiology`)
- [ ] Войти под ролью `cardio` (или `cardio@example.com` из `homeForUsernames`)
- [ ] Открыть очередь на сегодня — patients в статусе `waiting` видны
- [ ] Нажать "Вызвать" на пациенте — статус меняется на `called`
- [ ] Открыть вкладку "Визит" — `?tab=visit` синхронизируется в URL
- [ ] Заполнить EMR: complaint, diagnosis, icd10 (попробовать критический код I21 — должно показать `intent='danger'` confirm dialog)
- [ ] Нажать "Завершить приём" — ConfirmDialog с `intent='warning'` если не заполнены поля
- [ ] Подтвердить — `queueService.completeVisit` вызывает `POST /doctor/queue/{id}/complete`
- [ ] Тост "Прием завершен успешно"
- [ ] Автовызов следующего: тост "Вызван следующий пациент №X"
- [ ] Возврат на вкладку `queue`
- [ ] Проверить логи: `[Cardiology] loadEMR`, `[Cardiology] handleSaveVisit`

#### Dermatologist (`/doctor/dermatology`)
- [ ] Тот же флоу, плюс:
- [ ] Проверить интеграцию `PrescriptionSystem` — кнопка рецепта должна быть `disabled` если `canCreatePrescription=false`
- [ ] После завершения визита — `setEmr(null)`, `setPrescription(null)` сбрасываются
- [ ] Логи: `[Dermatology] handleSaveVisit`, `[Dermatology] callNextWaiting(dermatology)`

#### Dentist (`/doctor/dentistry`) ⚠️ Восстановлено в PR #1779
- [ ] Войти под ролью `dentist`
- [ ] Открыть вкладку "Записи" — выбрать визит с каноническим `visit_id`
- [ ] Нажать "Протокол визита" — откроется `VisitProtocol`
- [ ] Заполнить протокол: жалобы, процедуры, материалы, анестезия, рекомендации
- [ ] **NEW**: Нажать "Завершить приём" (синяя кнопка рядом с "Сохранить")
- [ ] Подтвердить — вызывается `handleCompleteVisit`:
  - `resolveDoctorQueueEntryId(selectedPatient)` → canonical id
  - `queueService.completeVisit(queueEntryId, payload)` → `POST /doctor/queue/{id}/complete`
  - Сброс: `setSelectedPatient(null)`, `setShowVisitProtocol(false)`, `setProtocolTemplateDraft(null)`
  - `handleTabChange('queue')`
  - `callNextWaiting(SPECIALTY_KEYS.DENTISTRY)` → автовызов
- [ ] Логи: `[Dentistry] handleCompleteVisit: start/payload/completeVisit OK/finish`
- [ ] **Регресс-проверка**: кнопка "Сохранить" по-прежнему работает (только persist EMR, без complete)

#### DoctorPanel (универсальный врач, `/doctor`) ⚠️ Stub
- [ ] **Известная проблема**: `loadData()` устанавливает пустые массивы `patients`/`appointments` без API-вызова (строка 215 в `DoctorPanel.jsx`)
- [ ] Все кнопки Edit/View/Complete/Cancel только `logger.log` (строки 1070, 1224)
- [ ] **Действие**: не тестировать как функциональную панель — это stub. Использовать специализированные панели (`/doctor/cardiology`, `/doctor/dermatology`, `/doctor/dentistry`)

### 1.2. Кросс-браузерная матрица

| Браузер | Версия | Особенности | Приоритет |
|---|---|---|---|
| Chrome | latest | Основной dev-браузер | P0 |
| Firefox | latest | Альтернатива для QA | P0 |
| Edge | latest | **Известная проблема с кэшированием** (см. Этап 4 в `UNIFIED_PANELS_IMPROVEMENT_PLAN.md`) | P0 |
| Safari | latest (macOS) | WebKit-специфика, IntersectionObserver | P1 |
| Safari iOS | latest | Touch-жесты, viewport | P2 |
| Chrome Android | latest | Mobile sidebar (P-018 fix) | P2 |

**Edge-specific проверки:**
- [ ] Открыть RegistrarPanel → переключить отделение → нажать F5 → состояние сохраняется (R-02 fix)
- [ ] Открыть DoctorPanel → сменить пациента → F5 → верный пациент
- [ ] Проверить `Cache-Control: no-store` на API-ответах очереди
- [ ] Если кэш всё же протекает — добавить `cache: 'no-store'` в fetch options для `getTodayQueue`, `fetchQueuesToday`

### 1.3. Real-time сценарии (требует включённого WS)

> ⚠️ **Текущее состояние**: `VITE_ENABLE_WS=0` по умолчанию → polling 30s в `useDoctorQueue.js`

Включить WS локально:
```bash
# frontend/.env.local
VITE_ENABLE_WS=1
```

- [ ] Открыть два браузера (или окно + incognito): врач и регистратор
- [ ] Регистратор добавляет пациента в очередь врача
- [ ] Врач должен увидеть нового пациента **без F5** (если WS работает)
- [ ] Если WS отключён — ждать до 30 секунд до следующего polling-цикла
- [ ] Разорвать соединение (DevTools → Network → Offline) на 10 секунд → проверить:
  - `openQueueWS` — **нет реконнекта** (известная проблема)
  - `openDisplayBoardWS` — 5 попыток × 3s, потом смерть
  - `NotificationWebSocketContext` — бесконечный 3s retry
- [ ] Восстановить соединение → проверить сходимость состояния

### 1.4. EMR v2 конфликт-резолюция (оптимистичная блокировка)

- [ ] Открыть один и тот же визит в двух вкладках (Tab A и Tab B) под одним врачом
- [ ] В Tab A — изменить complaint → автосейв (3s debounce)
- [ ] В Tab B — изменить diagnosis → автосейв
- [ ] Ожидание: Tab B должен получить 409 Conflict
- [ ] Проверить UI: `CONFLICT_DETECTED` action → диалог "Перезагрузить" / "Перезаписать"
- [ ] `reloadFromServer()` — загружает серверную версию
- [ ] `forceOverwrite()` — сохраняет с `row_version=0`
- [ ] Проверить `client_session_id` smart resolution: одна сессия в двух вкладках не должна конфликтовать сама с собой

### 1.5. Performance / load (опционально, для production-readiness)

- [ ] Профилирование bundle: `npm run build:analyze` в `frontend/`
- [ ] Lighthouse на `/doctor/cardiology`, `/registrar`, `/admin`
- [ ] Проверить lazy-loading: каждый чанк < 250 KB (см. `docs/audits/uiux-hard-audit-2026-05-20/bundle-performance-baseline-2026-05-22.md`)
- [ ] k6 load test: 50 одновременных регистраторов × 5 минут
- [ ] Проверить memory leaks: открыть DoctorPanel, сменить 50 пациентов подряд → heap не должен расти

### 1.6. Mobile / responsive

- [ ] iPhone SE (375px): sidebar collapsed, hamburger работает (P-018 fix)
- [ ] iPad (768px): sidebar expanded, full layout
- [ ] Touch targets ≥ 44×44px (a11y)
- [ ] Keyboard navigation: Tab через sidebar → main content → forms

### 1.7. Accessibility (a11y)

- [ ] `npm run audit:a11y` в `frontend/`
- [ ] `npm run audit:icon-controls` — иконочные кнопки должны иметь `aria-label`
- [ ] Axe DevTools на каждой панели — 0 critical violations
- [ ] Screen reader (VoiceOver / NVDA) — проверить:
  - Имя пациента читается при выборе
  - Статус очереди анонсируется
  - Toast-уведомления читаются (`aria-live="polite"`)
- [ ] Контраст текста ≥ 4.5:1 (WCAG AA)

---

## Часть 2. Оставшиеся проблемы и недостатки

### 🔴 P0 — Критические (требуют внимания до production)

#### P0-1. DoctorPanel — stub, не загружает данные
**Файл:** `frontend/src/pages/DoctorPanel.jsx:215`
**Симптом:** `loadData()` устанавливает `setPatients([])`, `setAppointments([])` без API-вызова. Все кнопки Edit/View/Complete/Cancel — только `logger.log`.
**Риск:** Пользователь с ролью `doctor` (без специализации) видит пустую панель. Если `homeForRoles` направляет его сюда, он не может работать.
**Действие:** Реализовать реальную загрузку через `useDoctorQueue` hook (как в специализированных панелях). Или: задокументировать как deprecated и направлять `doctor` на специализированные панели.

#### P0-2. Двойная система интерсепторов (race condition)
**Файлы:** `frontend/src/api/client.js` + `frontend/src/api/interceptors.js`
**Симптом:** Оба файла добавляют `Authorization: Bearer` header. Оба пытаются refresh token при 401. `client.js` — только логирует 401; `interceptors.js` — retry-after-refresh с `_retry` флагом.
**Риск:** При 401 оба интерсептора могут попытаться refresh token параллельно → двойной запрос на `/auth/refresh` → один из них получит устаревший refresh token → пользователя разлогинивает.
**Действие:** Консолидировать в одном файле. `interceptors.js` должен только добавлять logging/toast, а авторизация — в `client.js`. Удалить дублирование Bearer-заголовка.

#### P0-3. Cardiologist всё ещё использует raw fetch вместо EMRContainerV2
**Файл:** `frontend/src/pages/CardiologistPanelUnified.jsx:1230` (`loadEMR`)
**Симптом:** Cardio вызывает `fetch('/api/v1/v2/emr/{visitId}')` напрямую, минуя `<EMRContainerV2>` и `useEMR` reducer.
**Риск:** Нет optimistic locking, нет conflict resolution, нет autosave (3s debounce), нет undo/redo. Локальный `visitData` state в Cardio может рассинхронизироваться с backend.
**Действие (большой рефакторинг):** Перевести Cardio на `<EMRContainerV2>` как Dermatologist. Сохранить API совместимость. Это ~200-300 строк изменения — следующий PR.

---

### 🟠 P1 — Серьёзные (важно для production, но не блокирующие)

#### P1-1. WebSocket для очереди отключён по умолчанию
**Файл:** `frontend/src/api/ws.js:7` (`VITE_ENABLE_WS=0`)
**Симптом:** Обновление очереди врача работает через polling каждые 30 секунд в `useDoctorQueue.js`.
**Риск:**
- UX-задержка: врач видит нового пациента через 30 секунд после добавления регистратором
- Нагрузка на backend: N врачей × 2 запроса/мин × 8 часов = тысячи лишних запросов
**Действие:**
1. Добавить реконнект в `openQueueWS` (по образцу `NotificationWebSocketContext` — бесконечный 3s retry)
2. Добавить авторизацию (token в query param, как в `openDisplayBoardWS`)
3. Включить `VITE_ENABLE_WS=1` в production env
4. Сохранить polling как fallback при потере WS

#### P1-2. Кэш только in-memory (теряется при reload)
**Файл:** `frontend/src/core/cache/cacheService.js`
**Симптом:** `cacheService` использует `Map` — не переживает F5.
**Риск:** Каждый reload заставляет перезагружать EMR, услуги, врачей, ICD-10 справочники. UX-задержка + лишняя нагрузка.
**Действие:** Добавить IndexedDB-уровень (через `idb-keyval` или `localforage`). Стратегия: in-memory first, IndexedDB as persistent cache, network as source of truth. Инвалидация по тем же тегам.

#### P1-3. Три раздельные WebSocket-системы без единого менеджера
**Файлы:**
- `frontend/src/api/ws.js` — `openQueueWS` (нет реконнекта)
- `frontend/src/api/ws.js` — `openDisplayBoardWS` (5 попыток, потом смерть)
- `frontend/src/contexts/NotificationWebSocketContext.jsx` — бесконечный 3s retry
**Риск:** Дублирование логики, разные стратегии восстановления, риск рассинхронизации.
**Действие:** Создать `frontend/src/core/ws/WSManager.js`:
- Единый класс с channel-подписками
- Configurable retry policy (linear / exponential backoff)
- Heartbeat (ping/pong) каждые 30s
- Auto-reconnect на `close` (кроме code 1000)
- Backpressure: если 100+ сообщений в очереди — drop старые

#### P1-4. Дублирование кода между панелями (12 функций, ~600 строк)
**Файлы:** Cardio / Derma / Dentist `*PanelUnified.jsx`
**Симптом:** В PR #1779 вынесены только 2 функции (`countAppointmentsByStatuses`, `normalizeNumericId`). Остались:
- `resolveDoctorQueueEntryId` (контракт требует в каждом файле — нельзя вынести)
- `getAllPatientServices`, `ensureCanonicalVisitId`, `appointmentSummaryItems`
- `loadXxxAppointments` (3 варианта)
- `handleAppointmentActionClick` switch
- `loadPatientFromUrl` pattern
**Риск:** Bug fix в одной панели не попадает в другие. Maintainability.
**Действие:** Вынести не-контрактные функции в `utils/doctorPanelShared.js` или `hooks/useDoctorAppointments.js`. Сохранить `resolveDoctorQueueEntryId` локально (контракт).

#### P1-5. Нет дедупликации для произвольных GET-запросов
**Файл:** `frontend/src/api/client.js`
**Симптом:** Single-flight pattern реализован для 5+ специфичных операций (token refresh, CSRF, profile, session validation, notifications, setup status). Для произвольных GET — нет.
**Риск:** При быстром переключении вкладок могут уйти параллельные идентичные GET-запросы.
**Действие:** Добавить generic request deduplication в axios interceptor. Ключ: `${method}:${url}:${JSON.stringify(params)}`. Окно: 200ms. Только для GET.

#### P1-6. `useVisitLifecycle` подключён только в Cardio
**Файлы:** Cardio — подключён (PR #1779, шаг 5). Derma / Dentist — не подключены.
**Симптом:** Derma и Dentist не инвалидируют кэш при смене визита через `useVisitLifecycle`. Утечка данных между пациентами возможна при rapid switching.
**Риск:** PHI leak risk (меньший, чем у Cardio, потому что Derma/Dentist используют `EMRContainerV2` который сам подключает `useVisitLifecycle`).
**Действие:** Подключить `useVisitLifecycle` в Derma и Dentist (минимальный патч — `onCleanup` сбрасывает local state).

---

### 🟡 P2 — Средние (tech debt, не критично)

#### P2-1. `setupInterceptors()` вызывается синхронно в `main.jsx`
**Файл:** `frontend/src/main.jsx:18`
**Симптом:** `setupInterceptors()` вызывается на верхнем уровне модуля, до монтирования React. Если интерсепторы выбрасывают ошибку (например, нет `csrfToken`) — приложение падает.
**Действие:** Обернуть в try/catch + логировать.

#### P2-2. Глобальный 429 cooldown не имеет escape hatch
**Файл:** `frontend/src/api/client.js` (60s cooldown с persisting в localStorage)
**Симптом:** После любого 429 все запросы блокируются на 60 секунд. Если 429 был случайным (например, другой вкладкой) — пользователь не может работать минуту.
**Действие:** Показывать toast "Сервер перегружен, повтор через X секунд" с обратным отсчётом. Добавить кнопку "Повторить сейчас" для критичных операций.

#### P2-3. LabPanel — минимальное логирование
**Файл:** `frontend/src/pages/LabPanel.jsx`
**Симптом:** Эталонная обработка ошибок (через `retryAction`), но логирование минимальное.
**Действие:** Добавить `logger.info/warn` для ключевых событий (как в Cardio). Низкий приоритет.

#### P2-4. Pre-existing lint warnings (13 штук)
**Файлы:** Cardio (8), Derma (2), Dentist (3)
**Симптом:** `prefer-const`, `react-hooks/exhaustive-deps`, `no-unused-vars` (Badge, Textarea в Cardio).
**Действие:** `npm run lint -- --fix` автоматически исправит 5. Остальные — ручной фикс.

#### P2-5. `formatHistoryTimestamp` определена, но не используется
**Файл:** `frontend/src/pages/CardiologistPanelUnified.jsx:1483`
**Симптом:** Dead code.
**Действие:** Удалить.

#### P2-6. EMR autosave не показывает статус пользователю
**Файл:** `frontend/src/hooks/useEMRAutosave.js`
**Симптом:** Autosave работает (3s debounce, 30s maxWait), но UI не показывает "Сохранение..." / "Сохранено" / "Ошибка".
**Действие:** Добавить badge в EMRContainerV2: `idle | saving | saved | error | paused`.

---

### 🟢 P3 — Низкий приоритет / tech debt

- **P3-1.** Mixed line endings (CRLF/LF) в `VisitProtocol.jsx` — был пропущен в PR #1779, пришлось патчить Python-скриптом.
- **P3-2.** Нет unit-тестов для `utils/doctorPanelShared.js` (только что создан). Добавить `__tests__/doctorPanelShared.test.js`.
- **P3-3.** `SPECIALTY_ALIASES` дублирует backend `DOCTOR_QUEUE_SPECIALTY_VARIANTS`. Можно вынести в кодогенерацию из OpenAPI.
- **P3-4.** В `useQueueManager.js` есть debug-логи `logger.log('[useQueueManager] ✅ Найдена очередь...')` — заменить на `logger.debug` или убрать.
- **P3-5.** Dentist `persistVisitProtocol` использует `rowVersion: 0` (skip lock check) — потенциальная потеря данных при concurrent edits.

---

## Часть 3. Направления для следующего аудита

### A1. Backend audit (не делался в PR #1779)

**Цель:** Проверить, что backend-контракты соответствуют frontend-ожиданиям.

**Шаги:**
1. Запустить `pytest backend/tests/integration/test_specialized_panels_api_endpoints.py` — все ли эндпоинты `/doctor/{specialty}/*` covered
2. Проверить `DOCTOR_QUEUE_SPECIALTY_VARIANTS` — все ли алиасы из frontend `SPECIALTY_ALIASES` есть
3. Аудит `available_actions` — backend реально возвращает корректный набор для каждого статуса
4. Проверить `require_roles()` на всех эндпоинтах `/doctor/*` — паритет с frontend `canAccessRoute`
5. Запустить `pytest backend/tests/integration/test_rbac_matrix.py` — 19/19 должно проходить
6. Проверить audit logs: `user_audit_logs` пишется при 403, при completeVisit, при mark_paid

**Артефакты:**
- `backend/tests/integration/test_rbac_matrix.py`
- `backend/tests/integration/test_specialized_panels_api_endpoints.py`
- `docs/ROLE_SYSTEM_PROTECTION.md`
- `docs/RBAC_VERIFICATION_REPORT.md`

---

### A2. Real-time reliability audit

**Цель:** Доказать, что WebSocket-система устойчива к сбоям сети.

**Шаги:**
1. Smoke-тест: 2 пользователя, отправка сообщения, проверка unread/read convergence
2. Force disconnect (DevTools Offline) — проверить реконнект каждой из 3 WS-систем
3. Long-running test (1 час) — проверить memory leaks в WebSocket listeners
4. Network throttling (Slow 3G) — проверить timeout/retry поведение
5. Concurrent edits (2 вкладки одного врача) — проверить conflict resolution
6. Проверить `client_session_id` — действительно ли smart resolution работает

**Артефакты:**
- `docs/NOTIFICATION_SYSTEM_ARCHITECTURE.md`
- `frontend/src/contexts/NotificationWebSocketContext.jsx`
- `frontend/src/contexts/ChatContext.jsx`

---

### A3. EMR v2 conflict resolution audit

**Цель:** Подтвердить, что optimistic locking + smart conflict resolution работают во всех сценариях.

**Шаги:**
1. Юнит-тесты: `hooks/__tests__/useEMR.test.js` (если нет — создать)
2. Integration: 2 вкладки → edit → save → conflict → reload/overwrite
3. Edge case: `row_version=0` (forceOverwrite) — проверить, что это не ломает последующие save
4. Edge case: `client_session_id` одинаковый → не должно быть конфликта
5. Edge case: autosave во время conflict → должен приостановиться
6. Edge case: 503 → exponential backoff (2x, max 60s)
7. Edge case: 401/403 → `writeAccessDeniedRef = true`, все последующие save сразу возвращают ошибку

**Артефакты:**
- `frontend/src/hooks/useEMR.js`
- `frontend/src/hooks/useEMRAutosave.js`
- `frontend/src/components/emr-v2/EMRContainerV2.jsx`
- `docs/EMR_V2_DOCTOR_GUIDE.md`

---

### A4. Security audit (PHI protection)

**Цель:** Подтвердить, что PHI (Protected Health Information) не утекает.

**Шаги:**
1. **Cache leak test**: открыть пациента A → сменить на пациента B → проверить, что в `cacheService` нет записей с тегом `visit:${A.visitId}` (после `invalidateByVisit`)
2. **State leak test**: открыть пациента A → заполнить EMR → сменить на пациента B → проверить, что `setEmr(null)` сработал (в Cardio)
3. **Network leak test**: открыть DevTools Network → сменить пациента → проверить, что in-flight запросы aborted (через `AbortController` в `useVisitLifecycle`)
4. **localStorage leak test**: проверить, что в localStorage нет patient-specific данных (только `auth_token`, `auth_profile`)
5. **URL leak test**: `?patientId=42` в URL — проверить, что SpeedInsights санитизирует (`sanitizeSpeedInsightsEvent`)
6. **Logger leak test**: проверить, что `utils/logger.js` фильтрует PHI-поля (`PHI_FIELDS`)
7. **Audit log test**: проверить, что backend пишет `user_audit_logs` при доступе к EMR

**Артефакты:**
- `docs/SECURITY_CHECKLIST.md`
- `docs/PRODUCTION_SECURITY.md`
- `frontend/src/utils/logger.js` (PHI_FIELDS)
- `frontend/src/utils/speedInsightsPrivacy.js`

---

### A5. Performance audit

**Цель:** Подтвердить, что bundle size и runtime performance в норме.

**Шаги:**
1. **Bundle analysis**: `npm run build:analyze` в `frontend/`
   - Каждый lazy-chunk < 250 KB (gzipped)
   - Total initial bundle < 200 KB
   - Проверить `docs/audits/uiux-hard-audit-2026-05-20/bundle-performance-baseline-2026-05-22.md`
2. **Runtime profiling**: React DevTools Profiler на каждой панели
   - Время mount < 100ms
   - Re-renders при печати в EMR — не больше 1 в 100ms
3. **Network profiling**: Lighthouse на `/doctor/cardiology`
   - LCP < 2.5s
   - FID < 100ms
   - CLS < 0.1
4. **Memory profiling**: открыть панель, сменить 50 пациентов → heap snapshot → проверить, что нет leak
5. **Database profiling** (backend): slow queries > 100ms → добавить индексы

**Артефакты:**
- `docs/audits/uiux-hard-audit-2026-05-20/`
- `docs/architecture/performance-checklist.md`
- `docs/architecture/performance-lessons.md`

---

### A6. Accessibility (a11y) audit

**Цель:** WCAG 2.1 AA compliance.

**Шаги:**
1. `npm run audit:a11y` — eslint a11y rules
2. `npm run audit:icon-controls` — иконочные кнопки без `aria-label`
3. `npm run audit:icon-controls:components` — то же для компонентов
4. Axe DevTools — 0 critical violations на каждой панели
5. Keyboard navigation: Tab / Shift+Tab / Enter / Escape работают во всех формах
6. Screen reader: VoiceOver (macOS) / NVDA (Windows) — проверить анонсы
7. Цветовой контраст: WebAIM Contrast Checker — ≥ 4.5:1 для текста, ≥ 3:1 для крупного

**Артефакты:**
- `docs/audits/uiux-hard-audit-2026-05-20/global-icon-only-controls-a11y-sweep.md`
- `docs/audits/uiux-hard-audit-2026-05-20/pass-c-browser-visual-accessibility.md`
- `frontend/scripts/a11y/`

---

### A7. State management audit

**Цель:** Понять, где state дублируется и какие хуки можно объединить.

**Шаги:**
1. Составить карту state: `useState` × панель × поле
2. Найти дубликаты: например, `selectedPatient` может быть в `useDoctorPanelState` + локально в панели
3. Проверить prop drilling: `patientId` передаётся через 3+ уровня?
4. Оценить переход на Zustand / Jotai для global state (сейчас `stores/auth.js` — кастомный)
5. Проверить React 18 concurrent features: `useTransition`, `useDeferredValue` для тяжёлых списков

**Артефакты:**
- `frontend/src/stores/`
- `frontend/src/hooks/`
- `frontend/src/contexts/`

---

### A8. Test coverage audit

**Цель:** Найти непокрытые тестами критичные пути.

**Шаги:**
1. `cd frontend && npx vitest run --coverage`
2. Найти файлы с coverage < 70%:
   - `pages/DentistPanelUnified.jsx` (3600 строк — наверняка < 50%)
   - `pages/DoctorPanel.jsx` (1700 строк stub)
   - `services/queue.js` (нет unit-тестов)
3. Добавить contract-тесты для:
   - `queueService.completeVisit` → mock fetch → проверить payload
   - `queueService.callNextWaiting` → mock fetch → проверить selectNextCallEntry
   - `useVisitLifecycle` onCleanup callback
4. Backend: `pytest --cov=backend/app` → найти эндпоинты без тестов

**Артефакты:**
- `frontend/src/pages/__tests__/`
- `backend/tests/`

---

### A9. Operational readiness audit (production deployment)

**Цель:** Подтвердить, что система готова к pilot-запуску в клинике.

**Шаги:**
1. Пройти `docs/runbooks/CLINIC_PRE_RELEASE_CHECKLIST.md`
2. Пройти `docs/runbooks/CONTROLLED_PILOT_GATE_CHECKLIST.md`
3. Проверить `docs/runbooks/PILOT_START_CHECKLIST.md`
4. Проверить `docs/runbooks/OBSERVABILITY_SLA_RUNBOOK.md` — метрики, алерты, dashboards
5. Проверить `docs/runbooks/POSTGRES_DR_RUNBOOK.md` — backup/restore процедуру
6. Проверить `docs/runbooks/CLINIC_BACKUP_RESTORE_REHEARSAL_RUNBOOK.md` — dry-run восстановления
7. Smoke-тест: `docs/ADM-06_BROWSER_SMOKE.md`

**Артефакты:**
- `docs/runbooks/`
- `docs/release_gates/`

---

## Часть 4. Приоритезация следующих PR

| Приоритет | PR | Описание | Effort | Риск |
|---|---|---|---|---|
| 1 | `fix(doctor-panel): implement real data loading` | P0-1 — DoctorPanel stub | Medium | Low |
| 2 | `refactor(api): consolidate interceptors` | P0-2 — двойные интерсепторы | Medium | Medium |
| 3 | `refactor(cardio): migrate to EMRContainerV2` | P0-3 — Cardio raw fetch | Large | High |
| 4 | `feat(ws): enable queue websocket + reconnect` | P1-1 — WS отключён | Medium | Medium |
| 5 | `feat(cache): add IndexedDB persistence` | P1-2 — кэш теряется при reload | Large | Medium |
| 6 | `refactor(ws): unified WSManager` | P1-3 — 3 раздельные системы | Large | Medium |
| 7 | `refactor(panels): extract more shared helpers` | P1-4 — 600 строк дублирования | Medium | Low |
| 8 | `feat(api): generic GET deduplication` | P1-5 — нет дедупликации | Small | Low |
| 9 | `feat(derma,dentist): wire useVisitLifecycle` | P1-6 — PHI leak prevention | Small | Low |
| 10 | `chore(lint): fix pre-existing warnings` | P2-4 — 13 warnings | Small | Low |

**Рекомендация:** делать по 1 PR в неделю, каждый ≤ 500 строк diff, каждый — с полным набором контрактов и CI.

---

## Часть 5. Quick wins (можно сделать облачно, без запуска проекта)

Если хочется продолжить работу облачно, вот задачи, не требующие локального запуска:

- [x] ✅ **Добавить unit-тесты для `utils/doctorPanelShared.js`** — 33 теста covering SPECIALTY_KEYS, SPECIALTY_ALIASES, matchesSpecialty, countAppointmentsByStatuses, normalizeNumericId (closed in PR follow-up)
- [x] ✅ **Удалить dead code**: `formatHistoryTimestamp` в Cardio (P2-5) + unused `Badge` import (closed in PR follow-up)
- [x] ✅ **Заменить debug-логи** в `useQueueManager.js` на `logger.debug` (P3-4) (closed in PR follow-up)
- [x] ✅ **Fix pre-existing lint warnings** (P2-4) — 13 → 5 warnings (remaining 5 are `react-hooks/exhaustive-deps` requiring manual hook analysis)
- [x] ✅ **Документировать P0-2 (двойные интерсепторы)** в виде ADR (`docs/architecture/ADR-0002-interceptor-consolidation.md`) — Proposed status, 3-phase plan
- [x] ✅ **Создать `docs/architecture/ADR-0003-cardio-emr-v2-migration.md`** с планом миграции Cardio на EMRContainerV2 — Proposed status, 4-phase plan
- [x] ✅ **Подключить `useVisitLifecycle` в Derma и Dentist** (P1-6) — закрыто, все 3 панели теперь симметричны

### Остались облачные задачи (не сделаны):

- [x] ✅ **Вынести ещё shared helpers** из панелей (P1-4) — `getAllPatientServices` и `makeEnsureCanonicalVisitId` factory вынесены в `utils/doctorPanelShared.js`
- [x] ✅ **Fix оставшихся 5 `react-hooks/exhaustive-deps` warnings** — все 5 исправлены (добавлены stable setState в deps)
- [x] ✅ **Создать ADR-0004** — план включения `VITE_ENABLE_WS=1` + реконнект в `openQueueWS` (P1-1) — Proposed, 3-phase plan
- [x] ✅ **Создать ADR-0005** — план unified WSManager (P1-3) — Proposed, 4-phase plan
- [x] ✅ **Создать ADR-0006** — план IndexedDB persistence layer для cacheService (P1-2) — Proposed, 4-phase plan

### Остались облачные задачи (ещё не сделаны):

- [ ] **Вынести ещё 3-4 shared helpers** — `appointmentSummaryItems`, `loadXxxAppointments` (3 варианта), `handleAppointmentActionClick` switch. Требует более глубокого анализа, т.к. эти функции имеют panel-specific variations.
- [ ] **Создать ADR-0007** — план generic GET-дедупликации в axios interceptor (P1-5)
- [ ] **Добавить unit-тесты для новых shared helpers** — `getAllPatientServices`, `makeEnsureCanonicalVisitId` (расширить `doctorPanelShared.test.js`)
- [ ] **Удалить 19 unused functions в DentistPanelUnified** — `loadTreatmentPlans`, `loadProsthetics`, `handleReports`, `handleTreatmentPlanner`, `filteredPatients`, `stats`, `renderAppointments`, `renderExaminations`, `renderDiagnoses`, `renderTemplates`, `renderReports`, `renderDentalChart` — likely dead code from god-component split (PR-44/45)
- [ ] **Удалить dead `openQueueWS`** в `api/ws.js:15` — 0 callers (ADR-0005 Phase 0)

---

## Re-audit 2026-07-13

После 448 коммитов в main (PR-26..PR-46, включая полный frontend+backend аудит), статус изменился:

### ✅ Закрыто командой (не нашими PR):
- **P1-1 (WS disabled)** — ЗАКРЫТ через `useQueueWebSocket` hook (PR-36, #2110). Exponential backoff, JWT subprotocol auth. ADR-0004 отмечен как Implemented.
- **P0-3 frontend audit (WS JWT in URL)** — частично закрыт: `NotificationWebSocketContext` + `websocketAuth.js` используют subprotocol, но **4 других WS-сайта всё ещё утекают JWT в URL** (новая находка — см. ADR-0005 update).
- **41 frontend audit finding** — все закрыты (PR-35..PR-44)
- **50 backend audit findings** — все закрыты (PR-1..PR-34)
- **Тесты: 517 → 626** (+109 новых)

### ❌ Всё ещё открыто:

| ID | Задача | Статус | Требует локального запуска |
|---|---|---|---|
| **P0-1** | DoctorPanel stub | `loadData()` setPatients([]) без API | ✅ Да |
| **P0-2** | Двойные интерсепторы | `client.js` + `interceptors.js` оба регистрируют | ✅ Да (401 flow) |
| **P0-3** | Cardio raw fetch | `fetch('/v2/emr/...')` вместо EMRContainerV2 | ✅ Да (smoke test) |
| **P1-2** | In-memory cache only | cacheService — Map only, нет IndexedDB | ✅ Да |
| **P1-3** | 7 раздельных WS-систем | ADR-0005 обновлён, 7 phases | ✅ Да |
| **P1-5** | GET-дедупликация | partial (messages.js only) | ✅ Да |
| **NEW** | 4 WS-сайта утекают JWT в URL | useQueueWebSocket, useAIChat, useApi, ChatContext | ✅ Да (security P0) |

### Новые находки (2026-07-13):
- **N1.** 4 из 7 WS-сайтов утекают JWT в URL query (`?token=...`) — regression от PR-36/P0-3
- **N2.** ChatContext.jsx:357 — WS без auth вообще
- **N3.** 19 unused functions в DentistPanelUnified (dead code от god-component split)
- **N4.** Dead `openQueueWS` в api/ws.js — 0 callers

---

**Дата создания:** 2026-07-04
**Обновлено:** 2026-07-13 — re-audit после 448 коммитов в main
**Автор:** dr-sapaev-bot
**Статус:** Partially closed — P1-1 закрыт командой, P0-1/P0-2/P0-3/P1-2/P1-3 требуют локальной разработки
**Связанные merged PR:**
- #1779 (`c77aa2b`) — основной workflow refactor
- #1780 (`e2e15a9`) — этот follow-up документ
- #1789 (`8913f31`) — cloud follow-up: useVisitLifecycle, tests, dead code, ADR-0002/0003
