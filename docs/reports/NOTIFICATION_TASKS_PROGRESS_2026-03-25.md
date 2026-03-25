# Notification roadmap: фактический прогресс и следующий логический шаг

Дата проверки: 2026-03-25
Основание: текущий HEAD репозитория

## Что проверено

Проверка сделана по четырём задачам из плана:

1. унифицировать frontend notification layer;
2. убрать `alert(...)` из panel workflows;
3. внедрить inbox + realtime для Doctor / Registrar / Lab / Patient;
4. выровнять backend/frontend contract общего notifications API.

## Статус по задачам

| Задача | Статус | Комментарий |
|---|---|---|
| 1. Унификация frontend notification layer | ⏳ Частично | Глобально подключены `ToastProvider` + `NotificationWebSocketProvider` + `NotificationPrompt`, но одновременно широко используется `react-toastify`, значит единый слой пока не завершён. |
| 2. Убрать `alert(...)` из panel workflows | ❌ Не выполнено | В `AdminPanel` и `CashierPanel` остаётся много `alert(...)`, также `alert(...)` есть в отдельных панелях/компонентах. |
| 3. Inbox + realtime для Doctor/Registrar/Lab/Patient | ❌ Не выполнено | Нет отдельного `NotificationInbox/NotificationCenter` для этих ролей; Doctor/Lab/Patient панели не показывают полноценный inbox-поток уведомлений. |
| 4. Выравнивание backend/frontend contract notifications API | ⏳ Частично | Общий `notificationsService` есть, но он пока не стал центральной точкой потребления для ключевых панелей. |

## Доказательства (repo-grounded)

### Для задачи 1 (унификация слоя)

- Глобальные провайдеры уже подключены в приложении: `ToastProvider`, `NotificationWebSocketProvider`, `NotificationPrompt`.
- Но прямые импорты `react-toastify` остаются в ключевых панелях/хуках (`RegistrarPanel`, `DermatologistPanelUnified`, `DentistPanelUnified`, `useApi`, `FCMManager`).

### Для задачи 2 (удаление alert)

- `CashierPanel` использует `alert(...)` в основных платёжных сценариях (успех/ошибка/отмена/возврат/чек/статистика).
- `AdminPanel` использует `alert(...)` в рабочих сценариях (валидация, экспорт/импорт, удаление, деактивация врача и др.).

### Для задачи 3 (inbox + realtime)

- `DoctorPanel` содержит push-вызов для отдельного действия, но без inbox-центра уведомлений.
- `LabPanel` — в основном контейнер workbench-компонентов, без отдельного центра уведомлений в panel-shell.
- `PatientPanel` остаётся mock-ориентированной (локальные данные через `setTimeout`), без inbox/read-state.

### Для задачи 4 (frontend/backend contract)

- Во frontend есть общий `notificationsService` (list/get/mark-read/mark-all-read/send/types), но он не выглядит основным механизмом, через который живут panel notifications.

## Ответ на вопрос "что следующий логический шаг?"

Следующий логический шаг — **не сразу делать все 4 задачи параллельно**, а сделать узкий вертикальный срез, который разблокирует остальные:

## ✅ Next Step (Sprint 1): "Notification Adapter + Pilot Migration"

### Цель спринта

За 1 итерацию создать единый frontend adapter уведомлений и перевести на него 2 наиболее критичных панели с `alert(...)`:

- `CashierPanel`
- `AdminPanel`

### Почему это логично именно сейчас

- Это закрывает самый болезненный UX-долг (`alert(...)`).
- Это создаёт единый API (`notify.*`) перед внедрением inbox/realtime.
- Это уменьшает риск: не трогаем сразу всю систему, а даём контролируемый pilot.

### Scope Sprint 1 (конкретно)

1. Добавить модуль `frontend/src/services/notifications/uiNotifications.js` с API:
   - `success`, `error`, `info`, `warning`.
2. Реализовать его поверх текущего выбранного механизма (на этапе pilot можно через `react-toastify` или через внутренний `ToastProvider`, но только один вариант внутри adapter).
3. Мигрировать `alert(...)` в:
   - `frontend/src/pages/CashierPanel.jsx`
   - `frontend/src/pages/AdminPanel.jsx`.
4. Ввести линтер-правило/команду проверки (или хотя бы CI grep-check) на новые `alert(...)` в `frontend/src/pages`.
5. Добавить короткий `docs/` note: "как показывать уведомления через adapter".

### Definition of Done Sprint 1

- В `CashierPanel` и `AdminPanel` больше нет `alert(...)` для рабочих сценариев.
- Для обоих панелей используются только вызовы `notify.*`.
- Команда проверки блокирует появление новых `alert(...)` в `frontend/src/pages`.

## Что делать после Sprint 1

### Sprint 2

- Раскатать adapter на `RegistrarPanel`, `DermatologistPanelUnified`, `DentistPanelUnified`.
- Убрать прямые импорты `react-toastify` из panel-level файлов, где это возможно.

### Sprint 3

- Внедрить `NotificationInbox` + `NotificationStore` для Doctor/Registrar/Lab/Patient.
- Подключить realtime поток к inbox (не только toast-баннеры).

### Sprint 4

- Финально выровнять frontend/backend contract для notifications API и убрать legacy-вызовы.
