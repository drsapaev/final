# UI/UX audit — Medical Clinic SaaS (frontend)

**Путь:** `C:\final\UI_UX_audit_for_GPT.md`  
**Дата:** 2026-05-14  
**Метод:** статический аудит кода и маршрутизации (dev-серверы не обязательны). Если нужен живой браузер — поднять `frontend` (`npm run dev`, порт 5173) и `backend`.

---

## 0. Почему файла не было

Файл в рабочей копии отсутствовал (поиск по репозиторию `**/UI_UX_audit_for_GPT.md` — 0 совпадений). Документ **пересоздан** и закреплён в корне `C:\final\`.

---

## 1. Карта продукта (коротко)

| Слой | Назначение |
|------|------------|
| **Публичный маркетинг** | `Landing.jsx`, контент из `landingContent.js` |
| **Вход / онбординг** | `LoginFormStyled.jsx` (канон для `/login` в `routeRegistry.js`), отдельно существует legacy `pages/Login.jsx` |
| **App Shell** | `App.jsx` + `HeaderNew`, `Sidebar` (macOS UI), `RouteAccessBoundary` |
| **Ролевые панели** | Admin, Registrar, Doctor, Cashier, Lab, Patient, Cardio/Derma/Dentist unified |
| **Клинические тяжёлые зоны** | EMR v2 (`components/medical/emr-v2/`), очереди, платежи |
| **Демо / внутреннее** | `MacOSDemoPage`, `ButtonShowcase`, `IntegrationDemo` и др. по реестру |

**SSOT маршрутов:** `frontend/src/routing/routeRegistry.js` (+ `routeGuards.jsx`, `routeSelectors.js`).

---

## 2. Сильные стороны UX

1. **Единый каркас macOS** — `theme/macos-tokens.css`, `styles/macos.css`, компоненты `components/ui/macos`.
2. **Явный реестр маршрутов** — группы (`ROUTE_GROUPS`), жизненный цикл, оболочка (`ROUTE_SHELLS`), пресеты сайдбара `SIDEBAR_PRESETS`.
3. **Пациентский кабинет** — пустые состояния с понятными текстами («данные не подключены»), без фейковых демо-записей (`PatientPanel.jsx`).
4. **Очередь по QR** — богатая логика сессии, профили специалистов из API, события `queueUpdated` для панелей (`QueueJoin.jsx`).
5. **Доступность** — токены `A11Y_COLORS` используются в публичных потоках (логин, очередь).

---

## 3. Риски и проблемы (приоритеты)

### P0 — доверие, безопасность восприятия, консистентность

| ID | Проблема | Где | Рекомендация |
|----|-----------|-----|--------------|
| P0-1 | Два разных экрана входа: стилизованный канон и старый `Login.jsx` с дефолтом `admin@example.com` | `routeRegistry` → `LoginFormStyled`; `pages/Login.jsx` | Не использовать `Login.jsx` в прод-маршрутах; либо удалить/перенаправить, либо синхронизировать с `LoginFormStyled` и убрать дефолтные креды из UI. |
| P0-2 | Смешение языков в публичной очереди (RU комментарии + узбекские строки ошибок) | `QueueJoin.jsx` (пример: `getApiErrorMessage(..., 'Навбатга қўшилишда хатолик')`) | i18n-слой (RU по умолчанию для продукта + EN), без хардкода узбекского в общих ошибках или явный `locale` из клиники. |
| P0-3 | «AI-помощник» в сайдбаре без явного дисклеймера в навигации | `SIDEBAR_PRESETS` в `routeRegistry.js` | В подписи/тултипе: черновик, не диагноз; ссылка на политику; согласовано с EMR. |

### P1 — визуальная и архитектурная фрагментация

| ID | Проблема | Где | Рекомендация |
|----|-----------|-----|--------------|
| P1-1 | `PaymentSuccess.jsx` на **MUI**, остальной продукт на **macOS UI** | `pages/PaymentSuccess.jsx` | Переписать на `components/ui/macos` или общий «checkout result» паттерн. |
| P1-2 | `PaymentCancel` ведёт на `/support`, маршрута нет в `routeRegistry` (grep по файлу) | `PaymentCancel.jsx` → `navigate('/support')` | Добавить маршрут или заменить на существующий (Telegram, контакты лендинга, `mailto:`). |
| P1-3 | Несколько слоёв дизайна | `design-system/`, `ui/macos`, MUI, Tailwind-классы в панелях | Документ «что использовать когда»; постепенная консолидация платежей и крупных панелей. |
| P1-4 | Монолитные панели (тысячи строк) | `DoctorPanel`, `RegistrarPanel`, `QueueJoin`, др. | Разбить на фичи, общие empty/loading/error. |

### P2 — полировка

- Дублирование пресетов/иконок в сайдбаре (например два `list` у регистратора).
- Storybook / визуальные регрессии для критических страниц (опционально).
- E2E на happy-path: логин → роль → одна клиническая задача.

---

## 4. Ключевые файлы (для следующего агента)

```
frontend/src/App.jsx
frontend/src/routing/routeRegistry.js
frontend/src/routing/routeGuards.jsx
frontend/src/routing/routeSelectors.js
frontend/src/components/auth/LoginFormStyled.jsx
frontend/src/pages/Login.jsx                    # legacy / dev only
frontend/src/pages/Landing.jsx
frontend/src/pages/PatientPanel.jsx
frontend/src/pages/QueueJoin.jsx
frontend/src/pages/PaymentSuccess.jsx
frontend/src/pages/PaymentCancel.jsx
frontend/src/components/medical/emr-v2/...
frontend/src/components/ui/macos/...
```

---

## 5. Инструкции для GPT / AI Factory (промпт для плана)

Скопируйте в чат с `/aif-plan` или аналогом:

```text
Контекст: медицинский SaaS (React + Vite). UI SSOT: macOS design system в frontend/src/components/ui/macos и theme/macos-tokens.css. Маршруты: frontend/src/routing/routeRegistry.js.

Задача плана (UI/UX, первый спринт):
1) Убрать риск двойного логина: canonical LoginFormStyled на /login; решить судьбу pages/Login.jsx (redirect или удаление после проверки импортов).
2) PaymentSuccess: унифицировать с macOS UI вместо @mui/material.
3) PaymentCancel: исправить navigate('/support') — либо маршрут + страница, либо ссылка на реальный контакт.
4) QueueJoin: вынести строки в i18n; язык по умолчанию RU; убрать смешение uz/ru в пользовательских ошибках без явной локали клиники.
5) SIDEBAR_PRESETS: микрокопирайт для AI-разделов (draft / не медицинское заключение).

Ограничения: не трогать backend/auth контракт без задачи; не менять role SSOT; не массовый рефактор панелей — только перечисленные зоны. Валидация: npm run lint:check в frontend; ручной smoke на /login, /payment/success, /payment/cancel, публичный queue join URL.
```

---

## 6. Чеклист верификации после правок

- [ ] `/login` открывает только `LoginFormStyled`.
- [ ] Нет битой навигации с `/payment/cancel` (кнопка поддержки).
- [ ] `PaymentSuccess` визуально согласован с остальным приложением.
- [ ] Очередь: язык ошибок предсказуем для целевой аудитории (RU).
- [ ] Линтер frontend без новых ошибок в изменённых файлах.

---

*Конец документа.*
