# Отложенные дела (Deferred Backlog)

> Документ ведётся по ходу юзабилити-аудитов (ISO/IEC 25010 + Nielsen 10).
> Сюда попадают проблемы, которые **нельзя исправить в облачном окружении**
> (нужен backend/deps/data-migration/manual-deploy) или которые требуют
> отдельного scope за пределами точечного UI-fix.

**Обновлено:** 2026-07-15
**Активных задач:** 5 (DEFER-001 закрыт в PR #2299; DEFER-007 перенесён в Epic M4)

> **Важно:** Backend security & compliance задачи вынесены в отдельный эпик:
> **[docs/audit/epic-m4-backend-security.md](./epic-m4-backend-security.md)**
> (M4-P0-1 PHI Audit Trail, M4-P0-2 JWT transition, M4-P0-3 Session fixation и др.)
> Этот файл содержит только frontend-deferred items.

---

## Как использовать этот документ

- Каждая задача имеет ID, источник (какой аудит/панель обнаружила), контекст, почему отложено, и что нужно для выполнения.
- При завершении задачи — переместить в раздел «Выполнено» с указанием PR.
- Если в новом аудите находится задача, которую нельзя решить облачно — добавить сюда.

---

## Активные задачи

### DEFER-002 — MediLabDemo.jsx dead demo page (L-L-3)

- **Источник:** Lab Panel audit (L-L-3)
- **Симптом:** `frontend/src/pages/MediLabDemo.jsx` — 777 строк mock-данных, не используется в production routing, НО `CardiologistPanelUnified.jsx` / `DentistPanelUnified.jsx` / `DermatologistPanelUnified.jsx` проверяют `window.location.pathname.includes('/medilab-demo')` для demo-mode detection.
- **Почему отложено:** Удаление MediLabDemo.jsx сломает demo-mode detection в 3 specialist panels. Нужно сначала:
  1. Перенести demo-mode flag в env-variable или URL-param (`?demo=true`), ИЛИ
  2. Создать lightweight `useDemoMode()` hook, который не зависит от конкретного path.
- **Что нужно:** Сперва refactor demo-mode detection в specialist panels → затем удалить MediLabDemo.jsx + route registry entry.
- **Сложность:** Medium (4-6 часов, touch 3 panels + routing).
- **Блокирует:** Ничего критичного — demo-страница просто занимает место.

---

### DEFER-003 — i18n migration не завершена для lab-панели (L-M-6 partial)

- **Источник:** Lab Panel audit (L-M-6)
- **Симптом:** `labUiLabels.js` имел `getLabLabels(t)` i18n-обёртку (PR-73), но ни один компонент lab-модуля не использует `useTranslation` — все рендерят русские строки напрямую. В Batch B (PR #2294) `getLabLabels(t)` удалена как мёртвый код.
- **Почему отложено:** Полная i18n-миграция должна быть единой для всех панелей (Cashier/Registrar/Admin/Doctor/Lab), не точечно. Ни одна панель сейчас не использует `useTranslation` — это инфраструктурная задача.
- **Что нужно:**
  1. Подключить `react-i18next` (если ещё не подключён — проверить).
  2. Создать translation-keys для всех hardcoded-строк в lab-панели (~150 строк).
  3. Обновить компоненты: `import { useTranslation } from 'react-i18next'; const { t } = useTranslation();`
  4. Создать `getLabLabels(t)` заново — теперь с реальным consumer'ом.
- **Сложность:** High (8-12 часов для одной панели; ×5 для всех).
- **Блокирует:** Uzbek/English локализацию.

---

### DEFER-004 — Patient table pagination (Doctor M-16, Lab потенциально)

- **Источник:** Doctor Panel audit (M-16)
- **Симптом:** Patient table в DoctorPanel и потенциально в LabQueueWorkbench рендерит все записи без виртуализации. При 100+ записях — slowdown.
- **Почему отложено:** Нужно добавить `react-window` dependency (~30KB gzipped) — это требует команды `npm install` и пересборки lockfile. В облачном окружении нельзя надёжно установить новую dependency.
- **Что нужно:**
  1. `npm install react-window @types/react-window`
  2. Создать `FixedSizeList`-обёртку для patient rows.
  3. Обновить DoctorPanel + LabQueueWorkbench для использования виртуализации.
  4. Добавить Playwright e2e test для scroll-performance.
- **Сложность:** Medium (6-8 часов).
- **Блокирует:** Производительность на больших очередях (100+ пациентов).

---

### DEFER-005 — Backend endpoint для mark_ready (L-H-2 cleanup)

- **Источник:** Lab Panel audit (L-H-2)
- **Симптом:** Frontend cleanup (PR #2293) удалил `markReady()` method и `mark_ready` action mapping. Backend endpoint `POST /lab/report-instances/{id}/mark-ready` скорее всего всё ещё существует и возвращает 200/403 — но больше не вызывается.
- **Почему отложено:** Backend cleanup требует отдельного PR с backend-тестами. Нельзя проверить в облачном frontend-only окружении.
- **Что нужно:**
  1. Найти backend endpoint в `backend/app/api/v1/endpoints/lab_reporting.py` (или аналогичном).
  2. Проверить backend-тесты на `mark_ready` — если есть, удалить.
  3. Проверить RBAC rules, audit log и state machine transitions.
  4. Удалить endpoint + обновить OpenAPI schema.
- **Сложность:** Low (2-3 часа, но нужен backend).
- **Блокирует:** Ничего — frontend уже не вызывает endpoint. Просто dead-code на backend.

---

### DEFER-006 — Storybook stories для lab-панели

- **Источник:** Cross-panel consistency (Doctor panel имеет 22 stories, Lab — 0)
- **Симптом:** Lab-компоненты (LabQueueWorkbench, LabReportWorkbench, LabTemplateWorkbench, LabStatusStepper, LabReportAIAnalysis) не имеют Storybook stories. Doctor panel имеет 22 stories across 8 components.
- **Почему отложено:** Storybook stories требуют setup в `.storybook/` конфигурации, mock-data для backend-API, и визуальной верификации. В облачном окружении нельзя запустить Storybook для проверки.
- **Что нужно:**
  1. Создать `frontend/src/components/laboratory/__stories__/` directory.
  2. Для каждого компонента — 2-3 stories (default state, loading, error, empty).
  3. Mock `labReportingApi` через MSW или storybook-decorator.
  4. Добавить visual regression snapshots.
- **Сложность:** Medium (6-10 часов для 5 компонентов × 3 stories).
- **Блокирует:** Visual regression coverage для lab UI.

---

## Выполнено

### DEFER-001 — DoctorPanels.contract.test.jsx failure (РЕШЕНО в PR #2299)

- **Источник:** Doctor Panel audit (Batch H-30, PR #2292)
- **Решение:** PR #2299 обновил тест — marкеры ищут контракт в `components/doctor/DoctorQueuePanel.jsx` вместо `DoctorPanel.jsx`.
- **Статус:** ✅ Закрыто (2026-07-15)

### DEFER-007 — Optimistic locking для PatientFormsPreview (ПЕРЕНЕСЕНО в Epic M4)

- **Источник:** Patient Panel audit (P-H-7)
- **Решение:** Перенесено в **[Epic M4 — Backend Security & Compliance](./epic-m4-backend-security.md)** как часть комплексного backend-security epic. Optimistic locking зависит от backend-endpoint changes, логично делать вместе с audit trail и JWT transition.
- **Статус:** ✅ Перенесено в Epic M4 (2026-07-15)

---

## Шаблон для новой задачи

```markdown
### DEFER-XXX — Краткое название

- **Источник:** Какой аудит/панель обнаружила
- **Симптом:** Что观察到 — конкретная проблема
- **Почему отложено:** Что блокирует (backend/deps/data/visual verification)
- **Что нужно:** Пошаговый план выполнения
- **Сложность:** Low / Medium / High (с оценкой часов)
- **Блокирует:** Что не работает без этого
```
