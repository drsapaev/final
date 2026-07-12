# Frontend Audit — 2026-07-12

**Репозиторий:** `drsapaev/final/frontend/`
**Дата:** 2026-07-12
**Аудитор:** Super Z (z.ai)
**Объём:** 358 JSX файлов, ~208 678 LOC

---

## Сводка

| Severity | Кол-во |
|----------|--------|
| **P0** | 14 |
| **High** | 11 |
| **Medium** | 10 |
| **Low** | 6 |
| **Итого** | **41** |

---

## 1. Security

### P0-1. PHI в localStorage без шифрования
**Файл:** `src/components/mobile/OfflineIndicator.jsx:55-57, 94`
`cached_appointments`, `cached_patients`, `cached_notifications` — PHI (ФИО, телефоны, записи) в plaintext localStorage. При XSS или краже устройства — полное раскрытие.
**Фикс:** Удалить PHI-кеш или шифровать через WebCrypto API.

### P0-2. JWT токены в localStorage
**Файл:** `src/utils/tokenManager.js:9-14`
`auth_token` и `refresh_token` в localStorage. Комментарий признаёт риск. CSP с `unsafe-inline` (P0-6) не защищает.
**Фикс:** Мигрировать на httpOnly cookies (требует backend coordination).

### P0-3. JWT в URL query string WebSocket
**Файлы:** `src/api/ws.js:62`, `src/utils/websocketAuth.js:39`
Токен попадает в nginx access logs, browser history, Referer.
**Фикс:** `Sec-WebSocket-Protocol` subprotocol или post-connect message.

### P0-4. File upload без magic-number валидации
**Файл:** `src/utils/fileValidator.js` (мёртвый код — 0 импортов)
Все загрузчики используют только `accept` атрибут (UX-подсказка, легко обходится).
**Фикс:** Подключить `validateFile()` ко всем `<input type="file">`.

### P0-5. Санитайзеры не подключены к формам
**Файлы:** `src/hooks/useSafeInput.js`, `src/utils/sanitizer.js`
`sanitizeInput`, `sanitizeHTML`, `escapeHTML`, `sanitizeURL` — определены, но 0 продакшен-использования. Десятки форм отправляют данные без санитизации.
**Фикс:** Подключить `useSafeForm` к формам или документировать делегирование backend.

### P0-6. CSP с `script-src 'unsafe-inline'`
**Файл:** `docker/nginx.conf:14`
`unsafe-inline` отключает CSP-защиту от XSS. В связке с P0-2 (токены в localStorage) — критическая XSS-поверхность.
**Фикс:** Nonces или hashes вместо `unsafe-inline`.

### P0-7. `document.write(response.data.html)` без санитизации
**Файл:** `src/components/admin/BillingManager.jsx:218`
Backend-ответ пишется в новое окно без санитизации.
**Фикс:** `sanitizePrintableHtml(html)` (уже есть в `printWindow.js`).

### High-8. Нет HSTS, COOP, COEP в nginx
**Файл:** `docker/nginx.conf`
**Фикс:** Добавить security headers.

### High-9. Staging nginx без security headers
**Файл:** `docker/nginx.staging.conf`
**Фикс:** Скопировать security headers из prod config.

### Medium-10. CSP `connect-src` допускает `ws:` (любой origin)
**Фикс:** `connect-src 'self' wss://<api-origin>`.

### Medium-11. CSRF bootstrap отключён по умолчанию
**Файл:** `src/api/client.js:17`
**Фикс:** `VITE_CSRF_BOOTSTRAP=1` или backend cookie.

### Medium-12. JWT preview логируется в консоль
**Файл:** `src/api/client.js:202-207`
**Фикс:** Удалить в production-сборке.

---

## 2. Accessibility

### P0-A. Нет фокус-ловушки в большинстве модалок
**Файлы:** `components/ui/macos/Modal.jsx`, `Dialog.jsx`, `ResponsiveModal.jsx`
Tab уходит за пределы модалки. Фокус не возвращается на триггер.
**Фикс:** Hook `useFocusTrap` + восстановление фокуса.

### P0-B. Static `id="modal-title"` → коллизия
**Файл:** `components/ui/macos/Modal.jsx:123, 148`
**Фикс:** `useId()` (React 18+).

### P0-C. Контраст 3.49–4.14:1 (FAIL WCAG AA)
**Файлы:** `QueueTable.jsx:149`, `AppointmentWizardV2.jsx:2640`, `NotificationInbox.jsx:40`
**Фикс:** Более тёмные цвета foreground/background.

### High-D. Контраст 4.47:1 (borderline FAIL)
**Файл:** `AppointmentWizardV2.jsx:2626`

### Medium-E. `<label>` без `htmlFor` (6+ файлов)
**Фикс:** Массово добавить `htmlFor`/`id` association.

### Medium-F. `backgroundColor: 'white'` ломает dark mode
**Файлы:** `ResponsiveModal.jsx:109`, `ResponsiveForm.jsx:148`, `PhotoComparison.jsx:345`
**Фикс:** `var(--mac-bg-primary)`.

### Medium-G. `tabIndex={-1}` на action-иконках внутри input
**Файлы:** `forms/ModernInput.jsx:182,196`, `ModernSelect.jsx:252,354`
**Фикс:** `tabIndex={0}`.

---

## 3. Performance

### P0-13. N+1 API calls в Search.jsx
**Файл:** `src/pages/Search.jsx:79-93, 164-187`
Sequential `for` loops с `await api.get()` — до 10 запросов вместо 1 batch.
**Фикс:** `Promise.all` или backend batch endpoint.

### P0-14. Дублированный вызов в DentistPanelUnified
**Файл:** `src/pages/DentistPanelUnified.jsx:839-842`
`Promise.all([loadPatients(), loadPatients()])` — `loadPatients()` вызывается дважды.
**Фикс:** Удалить дубликат.

### High-15. God components (11 файлов >500 LOC)
Топ-5: `AppointmentWizardV2.jsx` (3015), `TelegramMiniAppPatientShell.jsx` (2601), `EnhancedAppointmentsTable.jsx` (2596), `TelegramManager.jsx` (2372), `DentistPanelUnified.jsx` (2349).
**Фикс:** Split по tab/view sub-components.

### High-16. Missing useMemo/useCallback (5 файлов с 0 memoization)
`TelegramManager.jsx` (2372 LOC, 0 useMemo), `CashierPanel.jsx` (1726 LOC, 0 useMemo), `QueueJoin.jsx` (1641 LOC, 0 useMemo), `DepartmentManagement.jsx` (1424 LOC, 0 useMemo).
**Фикс:** `useCallback` для handlers, `useMemo` для derived state.

### High-17. Large lists без virtualization
`AdminPatients.jsx` (до 1000 rows), `AdminAppointments.jsx` (unbounded). `react-virtual` установлен, используется 1 компонентом.
**Фикс:** `useVirtualizer` + pagination.

---

## 4. i18n

### P0-18. Три конкурирующих i18n системы
1. `src/locales/{ru,uz,en}.js` (2801 LOC) — **dead code, 0 импортов**
2. `src/hooks/useTranslation.jsx` — 4 файла
3. `src/pages/registrarTranslations.js` — RegistrarPanel only

`localStorage` key divergence: `useTranslation` → `language`, `RegistrarPanel` → `ui_lang`. Language switcher молча сломан для RegistrarPanel.
**Фикс:** Удалить dead `locales/`, унифицировать на `useTranslation`, единый `localStorage` key.

### P0-19. ~9400 hardcoded Russian strings
250 файлов. Покрытие i18n: 8 из 358 файлов (2.2%).
**Фикс:** Массовое извлечение в i18n keys (долгосрочная задача).

### High-20. Date/time/number formatting hardcoded `ru-RU`
48 вхождений `toLocaleDateString('ru-RU')`. `dateUtils.js` и `formatCurrency.js` default `ru-RU`.
**Фикс:** `useLocale()` driven by active language.

---

## 5. Code Quality

### High-21. 8 raw `fetch()` calls bypass axios client
**Файлы:** `usePatients.js` (6 calls), `DoctorPanel.jsx:302`, `CashierPanel.jsx:356`
Обходят auth/CSRF/refresh interceptors.
**Фикс:** Мигрировать на `api/patients.js`.

### High-22. Dead code (3400+ LOC)
- `src/locales/` — 2801 LOC, 0 импортов
- `src/hooks/useUtils.js` — 598 LOC, 0 реальных потребителей
- `src/components/examples/*` — 8 demo файлов
- `loadTreatmentPlans`/`loadProsthetics` stubs в DentistPanel
**Фикс:** Удалить.

### Medium-23. Silent catches (потерянные ошибки)
**Файлы:** `Search.jsx:71-73,90-92`, `DermatologistPanelUnified.jsx:776-778,820-822`
**Фикс:** `getErrorMessage(error)` + user-facing error toast.

### Medium-24. TODO/FIXME (5 штук)
`DentistPanelUnified.jsx:812-826` (stubs), `CashierPanel.jsx:1357`, `DermatologySection.jsx:75`, `fileValidator.js:308`.
**Фикс:** Удалить stubs, завести issues на реальные TODO.

---

## Положительные находки ✅

- ✅ `dangerouslySetInnerHTML` — 0 вхождений
- ✅ `eval()` / `new Function()` — 0 вхождений
- ✅ Все `<img>` имеют `alt`
- ✅ Все icon-only кнопки имеют `aria-label` (566 файлов, 0 findings)
- ✅ `role="button"` с `onKeyDown` (Enter/Space) — последовательно
- ✅ `.env` без секретов, только `VITE_*` public vars
- ✅ CSRF single-flight refresh mutex реализован
- ✅ DOMPurify установлен; AI-контент санитизируется
- ✅ `console.log` gated by `import.meta.env.MODE === 'development'`
- ✅ `prefers-reduced-motion` и `prefers-contrast: high` учитываются
- ✅ Focus-visible styles глобально
- ✅ Skip links на login page

---

## Рекомендуемый порядок исправлений

### Sprint 1 — Security P0 (7 находок)
1. P0-6: CSP убрать `unsafe-inline` → nonces/hashes
2. P0-7: `document.write` → `sanitizePrintableHtml`
3. P0-1: PHI-кеш в localStorage → удалить или шифровать
4. P0-3: WS JWT → subprotocol
5. P0-4: File upload → подключить `validateFile()`
6. P0-5: Санитайзеры → подключить к формам
7. P0-2: JWT → httpOnly cookies (backend coordination)

### Sprint 2 — A11y + Perf P0 (6 находок)
8. P0-A: Focus trap во всех модалках
9. P0-B: `useId()` вместо static ID
10. P0-C: Контрасты → WCAG AA
11. P0-13: N+1 в Search.jsx → `Promise.all` / batch
12. P0-14: Дублированный `loadPatients()` → удалить
13. High-8/9: Security headers в nginx (prod + staging)

### Sprint 3 — i18n + Quality (10 находок)
14. P0-18: Унификация i18n (удалить dead `locales/`, единый key)
15. High-20: `dateUtils`/`formatCurrency` locale-aware
16. High-21: 8 raw `fetch()` → axios client
17. High-22: Dead code cleanup (3400+ LOC)
18. Medium-E/F/G: a11y fixes (label htmlFor, dark mode, tabIndex)

### Sprint 4 — Long-term (8 находок)
19. P0-19: Массовое извлечение 9400 hardcoded strings
20. High-15: Split 11 god components
21. High-16: useMemo/useCallback для 5 файлов
22. High-17: Virtualization для AdminPatients/Appointments
23. Medium-23/24: Error handling + TODO cleanup
