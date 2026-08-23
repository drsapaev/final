# UI_AUDIT_PLAN — Аудит интерфейса и план унификации

> **Репозиторий:** github.com/drsapaev/final (фронтенд: `frontend/`)
> **Дата аудита:** 2026-08-23
> **Метод:** 5 параллельных глубоких аудитов (CSS/токены, компоненты, страницы, темы/UX/a11y, внутренняя документация) + перекрёстная валидация числовых метрик. Все числа получены реальными подсчётами (`rg -c` / `wc -l`) по коду, не оценками.
> **Статус:** документ заменяет собой разрозненные планы из ~91 MD-файла в `frontend/` и опирается на фактическое состояние кода, а не на заявления старых отчётов.

---

## Содержание

1. [Резюме (Executive Summary)](#1-резюме-executive-summary)
2. [Как мы пришли к хаосу: история миграций](#2-как-мы-пришли-к-хаосу-история-миграций)
3. [Карта проблем по слоям](#3-карта-проблем-по-слоям)
   - 3.1 Токены и CSS-архитектура
   - 3.2 Компонентный слой
   - 3.3 Страницы
   - 3.4 Оболочка, темы, UX-паттерны, a11y, i18n
   - 3.5 Документальный долг
4. [Сводный реестр находок (severity)](#4-сводный-реестр-находок-severity)
5. [Целевая архитектура](#5-целевая-архитектура)
6. [Поэтапный план исправлений (фазы 0–7)](#6-поэтапный-план-исправлений-фазы-07)
7. [Метрики успеха (текущее → цель)](#7-метрики-успеха-текущее--цель)
8. [Риски и правила безопасности миграции](#8-риски-и-правила-безопасности-миграции)
9. [Приложения](#9-приложения)

---

## 1. Резюме (Executive Summary)

**Масштаб проблемы.** Фронтенд — React 19 + Vite + TS: 481 TSX / 391 TS / 98 CSS файлов, 35 страниц (~29 600 строк TSX + ~7 700 строк CSS), 43 поддиректории компонентов (~364 файла). Интерфейс прошёл **минимум 6 волн миграций разными AI-агентами** (MUI → macOS UI → design-system/tokens → MUI v5 Enterprise → «Unified v2.0» → снова macOS), каждая волна оставила свой слой, и ни одна не была доведена до конца. Итог — интерфейс выглядит как 4–6 разных приложений.

**Ключевые числа (реальные подсчёты):**

| Метрика | Значение |
|---|---|
| Параллельных систем дизайн-токенов | **6** (`--mac-*`, legacy `--bg-*/--accent-color`, `--color-*`, `--surface-*`/emr, JS-токены `theme/tokens*.ts`, `A11Y_COLORS`) |
| Значений «primary blue» в коде | **6 разных hex** (`#007aff`×68, `#2563eb`×21, `#0ea5e9`×21, `#3b82f6`×20, `#6366f1`×6, `#0051d5`×4) |
| Токенов используется, но нигде не определено | **151** (369 `var()`-вызовов без fallback) |
| Inline-стилей `style={{}}` | **~2 600 вхождений в ~240 файлах** |
| Хардкод-цветов | **~1 127 в CSS + ~692 hex в 120 TSX** |
| `!important` | **357 в CSS + 80 в TSX** |
| Уникальных width-брейкпоинтов | **19** (хвост от 360 до 1536) |
| Значений font-size в px | **22 уникальных (629 деклараций, 8–48px)** |
| Значений border-radius | **30+ уникальных (940 деклараций)** |
| Вариантов font-family | **24 в CSS + 11 в inline** |
| Реализаций модальных окон | **22 файла вне кита + 2 внутри кита (Modal и Dialog одновременно)** |
| Реализаций таб-навигации | **≥6 в живых страницах** |
| Систем тостов | **2** (react-toastify 47 файлов + кастомный ToastProvider) |
| API пустых состояний | **5+** (MacOSEmptyState, AppEmpty, StateWrapper, PanelEmptyState, admin.css-классы) |
| Мёртвого кода | **~7 000+ строк** (7 мёртвых страниц ~2 000, ~20 мёртвых компонентов ~4 900, ~1 650 строк мёртвых CSS) |
| Документальный долг | **91 MD-файл / 26 207 строк**, минимум 4 взаимоисключающих «финальных» плана |

**Главный вывод.** Канон уже выбран и частично принят: UI-кит `src/components/ui/macos/` (35 компонентов, **228 файлов-импортёров**: Button 162, Input 135, Badge 100, Card 73+60) и токены `src/design-system/tokens.css` (`--mac-*` — **92% всех 13 326 `var()`-употреблений**). Проблема не в отсутствии системы, а в **недоведённом adoption (~60–65%)** и в патч-слоях поверх неё. Поэтому план ниже — не «ввести новую дизайн-систему», а **довести macOS-канон до 100%, распустить патч-слои и удалить мёртвые слои**.

**Что сломано прямо сейчас (прод-баги, чинить немедленно):**
1. `Toast.tsx` / `Modal.tsx` (общие провайдеры всего приложения) используют `--color-*`-токены, определённые **только в `src/styles/admin-styles.css`, который нигде не импортируется** → статусные цвета тостов и фоны модалок не работают глобально.
2. Модалка «Осмотр» в `DentistPanelUnified.tsx:2172–2300` свёрстана Tailwind-классами, которых в проекте нет (Tailwind не установлен), плюс `var(...)` вставлены прямо в `className` как имена классов → форма визуально сломана.
3. При явном выборе светлой темы пользователем с тёмной ОС интерфейс частично окрашивается тёмным (`@media (prefers-color-scheme: dark)`-блок в `macos.css:6–23` перебивает канонический токен-файл).

---

## 2. Как мы пришли к хаосу: история миграций

Хронология восстановлена из внутренней документации (источник — субаудит E; все утверждения привязаны к конкретным MD-файлам в `frontend/`).

| Период | Событие | След в коде сегодня |
|---|---|---|
| 19.12.2024 | «macOS UI v1» — панели переведены на `components/ui/macos` | Кит жив, adoption частичный |
| 11.01.2025 | Конфликт MUI×React → временные «Simple*»-компоненты | Удалены, следов нет |
| 2025 (до сент.) | Эпоха **4 параллельных систем**: design-system (Material, `#2196f3`) + theme/tokens (Tailwind, `#0ea5e9`) + MUI (68 импортов) + `clinic-*`-классы; этапы 2–5 «консолидации цветов» | `clinic-*` живы в `styles/theme.css`; 3 поколения primary-цвета |
| 16.09.2025 | «Критический фикс» тёмной темы хардкодами `#1e293b/#0f172a/#475569` | Хардкоды в `dark-theme-visibility-fix.css` |
| 28.02.2026 | **Два взаимоисключающих плана одной даты**: миграция «600+ компонентов на MUI v5» и одновременно «Unified Design System v2.0» на `unifiedTheme.js` | Ни один не реализован; `unifiedTheme.js` не существует; доки-призраки не помечены архивами |
| 15–20.05.2026 | Эпоха «macOS = канон»: UI Layer Contract; **MUI полностью удалён** (подтверждено: 0 `@mui`-импортов); UX-аудит 6.8/10; AppState-backlog | `DESIGN_SYSTEM.md` — контракт канона |
| 17.07.2026 | JS→TS-стабилизация: честно признано 55,6% файлов с `@ts-nocheck`; «regex-migration disaster» фаз 2–9 | Правило «один слайс за PR» |

**Уроки, которые код подтверждает:**
- Отчёты этапов 2–5 заявляли «100% хардкода цветов заменено» — фактически в коде сегодня ~1 800 хардкод-цветов. **Заявления старых отчётов нельзя считать истиной** — только проверяемые инвентари (образец честности — `MUI_RUNTIME_INVENTORY.md`).
- Миграция регексом по многим файлам уже один раз ломала семантику («regex-migration disaster»). Поэтому настоящий план построен на маленьких изолированных PR.
- В один день могли появиться два противоположных «целевых» плана. Поэтому здесь зафиксирован **один** канон с обоснованием (см. §5).

---

## 3. Карта проблем по слоям

### 3.1 Токены и CSS-архитектура (субаудит A)

#### 3.1.1 Шесть параллельных систем токенов

| Система | Где | Статус |
|---|---|---|
| `--mac-*` (~170 токенов, light+dark матрица) | `src/design-system/tokens.css` (676 строк) | **Канон** — 92% всех `var()` (12 257 из 13 326) |
| Legacy-алиасы `--bg-*/--text-*/--accent-color` | `src/styles/theme.css` (578) + дубли в `tokens.css` | Конфликтуют между собой (значения алиасов зависят от порядка импорта) |
| `--color-*` (~44 токена) | `src/styles/admin-styles.css` (379) | **Мёртвый файл, но его токены нужны живым Toast/Modal** (Critical) |
| `--surface-*/--accent-*/--space-*/--radius-*/--z-*` | `src/styles/emr-tokens.css` (327) | Жив (скрытый `@import` в theme.css); **dark-only палитра в безусловном `:root`** — EMR-поверхности тёмные даже в светлой теме |
| JS-палитры | `src/theme/tokens.ts` (498, «Single Source of Truth», primary `#0ea5e9`), `tokens-legacy.ts` (303, primary-шкала №3), `theme/tokens/` (6 файлов, 0 импортёров — мёртв), `constants/a11yTokens.ts` (`#0051D5` — палитра №4) | Runtime-мост `ThemeContext.tsx:350–429` пишет CSS-переменные из JS — второй источник правды |
| `--board-*` / `--landing-*` | `DisplayBoardUnified.tsx:638–658` (JS-объект тем), `Landing.css:13–15` | Локальные вселенные (частично оправданы: киоск/маркетинг) |

Всего: **490 определений custom properties / 327 уникальных имён / 82 имени определены более чем в одном файле** (163 избыточных определения); **16 имён имеют разные значения в разных файлах**.

#### 3.1.2 Конфликтующие токены (примеры)

| Токен | Значение A | Значение B | Кто побеждает |
|---|---|---|---|
| `--mac-bg-primary` (dark) | `#1c1c1e` (tokens.css:174, канон) | `#16171a` (macos.css:15) | macos.css (позже в каскаде) — **неканонично** |
| `--mac-text-primary` (dark) | `#ffffff` (tokens.css:179) | `#f3f4f7` (macos.css:18) | macos.css |
| `--text-primary` | `#f0f1f4` тёмный (emr-tokens.css:24) | `var(--mac-text-primary)` (theme.css:14) | theme/tokens — emr-значение молча перебито |
| `--shadow-sm/md/lg` | Tailwind-подобные (theme.css:30–32) | короткие (emr-tokens.css:109–111) | theme.css (порядок @import) |
| Базовый font-size | 13px (`--mac-font-size-base`) | 14px (`--radius-md` emr) / 16px (`fontSize.base` tokens.ts) | **три шкалы одновременно** |
| `radius-md` | 8px (`--mac-radius-md`) | 6px (`--radius-md` emr) / 4px-шаг (tokens.ts) | три шкалы |
| `z-dropdown` | 1000 (`--mac-z-*`) | 100 (`--z-*` emr) / 1000–1800 (tokens-legacy) | три несовместимые шкалы |
| `--accent-color`, `--info-color` | → `--mac-accent-blue` (theme.css:21,27) | → `--mac-accent` (tokens.css:22,26) | зависит от порядка импорта App.tsx:8–11 |

#### 3.1.3 Инвертированный каскад и патч-слои

Фактический порядок загрузки (единственная точка входа `src/main.tsx`):

```
emr-tokens.css (через @import в theme.css) → theme.css → dark-theme-visibility-fix.css
→ global-fixes.css → design-system/tokens.css → macos.css → header-new.css
→ react-toastify → components/admin/admin.css → lazy-CSS страниц
```

Проблемы:
- **Патчи грузятся раньше базы** (dark-fix и global-fixes перед tokens.css) и выживают только за счёт `!important` (44+33 шт.).
- `macos.css:6–23` содержит `@media (prefers-color-scheme: dark) :root {...}`, который грузится позже канона и перебивает его dark-палитру, а также навязывает тёмный фон при светлом выборе пользователя.
- «Спасательные» селекторы по инлайн-стилям: `div[style*="rgba(15, 23, 42, 0.8)"]` (dark-fix:41–63), `[style*=]`-блоки в `macos.css:415–465` — костыли поверх инлайн-стилей вместо их устранения.

#### 3.1.4 Мёртвые и конфликтующие CSS-файлы

| Файл | Строк | Статус | Проблема |
|---|---|---|---|
| `styles/accessibility.css` | 266 | **МЁРТВ (0 импортов)** | Skip-link, 44px touch, focus-visible, reduced-motion — вся a11y-слой выключен |
| `styles/admin-styles.css` | 379 | **МЁРТВ (0 импортов)** | Но только здесь определены `--color-*`, нужные живым Toast/Modal — Critical |
| `styles/cursor-effects.css` | 520 | МЁРТВ (упомянут только строкой в `utils/frontendAudit.tsx:309`) | Мусор |
| `theme/globalStyles.css` | 491 | МЁРТВ | Tailwind-подобные утилиты + опасное `outline:none !important` |
| `theme/tokens/` | 156 | МЁРТВ (0 импортёров) | Дубль шкал |
| `components/admin/admin.css` | **12 657** | LIVE | Utility-слой с классами-мутантами вида `.admin-d-block-fw-500-fs-dyn-col-dyn-mb-dyn`; внутри 50+ битых `var(--admin-*)` |
| 13 page-CSS (`doctor-`, `registrar-`, `cashier-`, `lab-`, `patient-`, `cardio-`, `dental-`, `derma-`, `qj-`, `pp-`, `settings-`…) | ~5 700 | LIVE | 8–11-й параллельные utility-диалекты: одни и те же `.flex/.text-sm/.p-4` переизобретены в каждом |

#### 3.1.5 Прочие метрики хаоса

- **@keyframes-коллизии**: `spin` определён ×17 файлов, `pulse` ×9, `fadeIn` ×8, `slideDown` ×6 — какая анимация сработает, зависит от того, чанк какого роута загрузился последним.
- **z-index**: 14 значений в CSS + `2147483647`×3 и `2147483000`×2 в TSX + 3 несовместимые токен-шкалы.
- Порядок импорта CSS дублируется в `main.tsx` и `App.tsx` (частично расходится), плюс точечные импорты глобальных CSS из lazy-страниц (`DoctorPanel.tsx:4`, `RegistrarPanel.tsx:16` тянут dark-fix повторно).

---

### 3.2 Компонентный слой (субаудит B)

#### 3.2.1 Кит `ui/macos` — частично принятый стандарт

Состав: 35 компонентов (Button, Card, Input, Select, Checkbox, Radio, SegmentedControl, Dialog, Modal, Sidebar, Skeleton, AppState-тройка, MacOSTab, MacOSEmptyState, MacOSStatCard/MetricCard/Pagination/Breadcrumb, Table, Tooltip, Avatar, Paper, Grid, List, Typography, Progress…).

| Adoption | Компоненты кита |
|---|---|
| ✅ Стандарт (>30 импортёров) | Button (162–164), Input (135), Badge (100), Card/MacOSCard (73+60), Select (61), Alert (49), Checkbox (49), Textarea (32), Icon (32), Skeleton (31), MacOSEmptyState (30) |
| ⚠️ Слабо (<15) | Dialog (14), SegmentedControl (14), AppEmpty/Loading/Error (13/10/10), Table (11), MacOSStatCard (9), MacOSTab (7), Label (6), Progress (5), Switch (4) |
| ❌ Игнорируются (0–2) | Avatar (0 — параллельно живёт `common/Avatar.tsx` с 10 hex), Paper (0), Radio (0), AnimatedTransition (0 — есть root-дубль), Sidebar/Grid/List/Option/Tooltip (2) |

Вывод: **базу не создавать заново** — консолидировать существующий кит и добить adoption.

#### 3.2.2 Дубли примитивов (реестр)

| Примитив | Реализаций вне кита | Примеры |
|---|---|---|
| **Модалки** | **22 файла** (13 `*Modal*` + 9 `*Dialog*`) + контекстная система в `common/Modal.tsx` (514 строк) + `ModernDialog` + ResponsiveModal | `admin/{User,Doctor,Patient,Appointment,Finance}Modal`, `dialogs/*`, `payment/CashPaymentModal`, `dental/ToothModal`, `emr-v2/{EMRHelp,EMRConflict}Dialog`. Внутри кита одновременно Modal.tsx и Dialog.tsx |
| **Таблицы** | 6 файлов | `ResponsiveTable` (469 стр., мёртв), `common/Table`, `queue/QueueTable`, `tables/EnhancedAppointmentsTable` (живой параллельный стандарт, 20 hex, 26 `!important` в CSS), `cashier/RefundRequestsTable`, `medical/MedicalTable` (мёртв) |
| **Кнопки** | 152 файла с локальными `<button>`/btn-классами | admin 27, emr-v2 23, dental 12 файлов; плюс IconButton/ChatButton/AIButton |
| **Формы** | Modern*-семейство (29 файлов): `ModernInput/Select/Textarea/Form` + `common/Form.tsx` | конкурируют с kit Input/Select |
| **Табы** | 3 именованных + рукописные табы почти в каждой панели (94 tab-класса в CSS) | см. §3.4.2 |
| **Лоадеры** | 6 подходов | AnimatedLoader, Skeleton, AppLoading, спиннеры, текст «Загрузка…» (захардкожен в 46 TSX) |
| **Empty-state** | 5+ API | MacOSEmptyState (30) vs AppEmpty (13) vs StateWrapper vs PanelEmptyState vs admin.css-классы |
| **2FA** | 6 файлов одной фичи | root `TwoFactor{Setup,Verify,Settings}` (2 мёртвых) + `security/*` (2 живых) |
| **Role-гварды** | 4 дубля | RoleGate / RoleGuard / ProtectedRoute / RequireAuth |
| **PWAInstallPrompt** | 3 копии (149/329/162 строк) | все без импортёров |
| **TelegramManager** | 2 копии | **root (2 496 строк) ЖИВОЙ** через `App.tsx:66`; `telegram/` (741) достижим только через мёртвую `TelegramPage.tsx` |
| **Confirm** | useConfirm (37 файлов — фактически стандарт) + остатки нативного `confirm()` (59 вхождений window.confirm/alert по всем файлам) | |
| **Иконки** | 4 подхода | lucide-react (210 файлов, 1 598 импортов — фактически стандарт), kit Icon (32), root `Icon.tsx` (1 импортёр), эмодзи (Search.tsx:355, EnhancedAppointmentsTable, DepartmentManagement) |

#### 3.2.3 Inline-стили и хардкод в компонентах

- **~2 100–2 220 `style={{}}` в ~174–206 файлах** (компоненты; вместе со страницами ~2 600).
- Топ по inline: `security/TwoFactorManager` 67, `auth/ForgotPassword` 60–62, `dental/DentalVisitScreen` 55, `ai/AIAssistant` 53–54, root `TelegramManager` 53, `files/FileManager` 51, `dermatology/SkinAnalysis` 51.
- Топ по hex: `auth/LoginFormStyled` 52–58, `emr-v2/TreatmentSection` 22–25, `tables/EnhancedAppointmentsTable` 20–30, `ui/FileUpload` 14.
- Inline-типографика: 688 inline `fontSize`, 474 `borderRadius`, 125 `boxShadow` — мимо токенов.
- Нативные `<select>` — 73 в 41 файлах при живом kit Select (61 импортёр); `title=` вместо Tooltip — 69 vs 9.

#### 3.2.4 Чистые и грязные домены (`style={{` на файл)

| Домен | Inline | Вердикт |
|---|---|---|
| dermatology | 268 / 8 файлов (34 на файл) | 🔴 самый грязный |
| admin | 172 / 40 | 🟠 размазано |
| cardiology | 103 / 7 (15/файл) | 🔴 |
| doctor | 95 / 3 (32/файл) | 🔴 |
| dental | 90 / 5 | 🔴 |
| emr-v2 | 67 / 9 + **24 собственных CSS** | 🟠 |
| laboratory | 66 / 8 | 🟡 |
| common | 62 / 9 | 🟡 |
| chat | 33 / 5 | 🟢 |
| patient | 12 / 2 | 🟢 |
| cashier | 3 / 1 | 🟢 эталон |

#### 3.2.5 Мёртвые компоненты (~4 900+ строк, проверено 0 импортёров)

`examples/` (10 файлов, кроме MacOSDemo), `test/ComponentTest`, `display/DisplayContentManager`, `forms/` (3 213 строк!), `ResponsiveTable` (469), `ResponsiveModal` (215), `layout/Modern*`, `ModernFilters`, `AppointmentPagination`, root `TwoFactorSetup/Settings` (1 174), `LanguageTest`, `ModernStatisticsSimple`, `medical/MedicalTable`, root `Icon.tsx`, 2 из 3 `PWAInstallPrompt`, осиротевшие CSS (`notifications/{ModernAlert,ModernToast,ModernProgressBar}.css`), `components/index.ts`.

---

### 3.3 Страницы (субаудит C)

#### 3.3.1 Мастер-таблица 35 страниц

Столбцы: стилизация / layout / inline-стили / визуальный стиль. Полная версия с точными счётчиками — в материалах аудита; здесь — сгруппированная карта.

| Группа | Страницы | Общее в группе |
|---|---|---|
| **Unified-панели специалистов** (одна система: `useDoctorPanelState`, fullscreen + sidebar `?tab=`) | CardiologistPanelUnified (2 054 стр., cardio.css 552), DentistPanelUnified (2 419, dentistry.css 724 + **сломанная Tailwind-модалка**), DermatologistPanelUnified (1 961, derma.css 562) | macOS-utility, но каждая со своим CSS-диалектом |
| **Основные панели** | DoctorPanel (1 330; **двойная навигация**: sidebar + свои inline-табы с JS-hover), RegistrarPanel (2 240; самая зрелая: ModernTabs + EnhancedAppointmentsTable + декомпозиция в `pages/registrar/`), CashierPanel (2 125; MacOSTab + SegmentedControl — единственная на китовских табах; 4 своих `<table class="cashier-table">`), LabPanel (815; **лучшая a11y**: tablist с клавиатурой; карточная очередь вместо таблиц), PatientPanel (403; tablist `pp-*`, чистая) | Смесь подходов |
| **Админка** | Settings (888; **вторая токен-система** `--bg-primary/--accent-color`, свои TabButton inline, вкладки не в URL), AnalyticsPage (1 181; 68 inline, 7 табов = ряд Button с inline-тенями, самописные KPI-карточки при живых MacOSStatCard), Audit, Appointments (чекбокс переключает raw-table ↔ Enhanced), Scheduler (единственная на `clinic-ops-*`), Search (764; стили-объект в файле, эмодзи-иконки), UserProfile (858; без CSS, 39 inline), UserSelect | app-shell, но свой стиль на страницу |
| **Публичные / fullscreen** | Landing (806 + Landing.css 1 081; собственная система `--landing-*`, 58 rgba, glass-эффект в JS `buildGlassStyle`), QueueJoin (1 554; `qj-*`, 77 inline, 9 мёртвых Tailwind-обёрток), Setup (830; **эталон**: Setup.css на `--mac-*`, медиа-запросы, инлайны выпилены), Login (реальный — `components/auth/LoginFormStyled.tsx` 892 стр., 43 inline, 53 hex-fallback), DisplayBoardUnified (997; киоск, 4-я система токенов `--board-*` — оправданно), Health | Каждая — своя вселенная |
| **Платежи** | PaymentSuccess (23 inline + собственный keyframes), PaymentCancel, PaymentTest (internal-demo) | inline-подход |
| **Telegram** | TelegramMiniAppPatientShell (2 328; монолит, все стили — ~50 CSSProperties-констант в конце файла) | автономно, монолит |
| **Мёртвые (0 достижимых роутов)** | Activation (184), SecurityPage (257), TelegramPage (148), FileSystemPage (156), MobilePatientDashboard (387), pages/Login (5), PublicApp.tsx | ~2 000+ строк; 4 из них на «мёртвом Tailwind» |
| **internal-demo в прод-роутах** (`routeRegistry.ts:1284–1372`, Admin-only, `nav:false`) | `/internal-demo/{medilab,macos,integration,payment-test,css-test}` — ~3 000+ строк в бандле; MediLabDemo тащит 4-е семейство UI-компонентов `components/medical/*` | вынести за флаг сборки |

Агрегаты по страницам: **371 inline `style={{}}`**, 68 строк с hex (почти все — fallback в `var()`), 13 CSS-файлов = 7 704 строки, 11 utility-префиксов (~5 700 строк).

#### 3.3.2 Монолиты (44% кода страниц)

Dentist 2 419 + TG-Shell 2 328 + Registrar 2 240 + Cashier 2 125 + Cardio 2 054 + Derma 1 961 = **13 127 строк** в 6 файлах.

#### 3.3.3 «Одно и то же по-разному» (готовый список для унификации)

| Сущность | Реализации |
|---|---|
| Таб-навигация (≥6) | DoctorPanel рукописные кнопки+JS-hover ≠ Registrar ModernTabs ≠ Cashier MacOSTab ≠ Lab `Button role="tab"` ≠ Analytics ряд Button ≠ Settings TabButton inline ≠ Patient `pp-tablist`. В ките есть MacOSTab |
| Список пациентов (4 парадигмы) | DoctorPanel raw-таблица ≠ Derma рукописные карточки в панели ≠ Dentist вынесенный DentalPatientsTab ≠ Registrar EnhancedAppointmentsTable |
| Таблицы (4+) | cashier-table ×4 ≠ Enhanced ≠ inline-table ≠ карточные workbench'и Lab; бонус: чекбокс-переключатель двух таблиц внутри одной страницы (`Appointments.tsx:138–164`) |
| Формы настроек (3 слоя) | Settings (legacy-токены) ≠ UserProfile (macos Input + inline) ≠ UnifiedSettings (admin) |
| Хлебные крошки (2) | `lab-breadcrumb-*` ≠ `pp-breadcrumb` (в ките есть MacOSBreadcrumb) |
| Стеклянная карточка (3) | QueueJoin `.qj-glass-card` ≠ Landing `buildGlassStyle()` ≠ LoginForm inline-градиенты |
| Empty-state (3 на страницах) | MacOSEmptyState ≠ DoctorPanel `renderEmptyState` ≠ AnalyticsEmptyState |

#### 3.3.4 Эталоны (куда вести остальные)

- **LabPanel** — a11y-tablist + декомпозиция на workbench-компоненты.
- **Setup.css** — образец миграции CSS на `--mac-*` с медиа-запросами.
- **PatientPanel** — tailwind→css миграция уже выполнена вручную (фиксируется комментарием в шапке).
- **RegistrarPanel** — path-based sidebar + ModernTabs + декомпозиция в `pages/registrar/` (в `registrar.css:14–29` уже есть deprecation-нотис на свои utility-классы).

---

### 3.4 Оболочка, темы, UX-паттерны, a11y, i18n (субаудит D)

#### 3.4.1 Тёмная тема — 4 слоя костылей

1. Токены `design-system/tokens.css` (light/dark матрица `.light-theme/.dark-theme` **и одновременно** `@media` — двойной механизм).
2. Legacy-алиасы `theme.css` со светлыми хардкодами (`#f1f5f9`).
3. Runtime-мост `ThemeContext.tsx:350–429` — JS пишет CSS-переменные через `style.setProperty` (второй источник правды).
4. Патч `dark-theme-visibility-fix.css` — 53 `!important`-селектора, включая выборки **по инлайн-стилям** (`div[style*="rgba(15, 23, 42, 0.8)"]`).

Причины, почему патчи необходимы: **2 620 inline-стилей** (нельзя перекрасить из CSS) и **182 JS-ветвления `isDark` в 29 файлах** (MedicalTable 26, DoctorCalendar 21, QueueProfilesManager 18, MetricCard 18). Dark-селекторы есть только в **19 из 98 CSS-файлов**; у doctor/cashier/lab/patient/dentistry/derma/cardiology/Landing CSS их 0.

Также: `colorScheme.ts` применяет тему **4 конвенциями классов + 2 data-атрибутами** сразу; синхронизация с `/users/me/preferences` (debounce 400ms); 5 localStorage-ключей; мёртвые ветки удалённых тем vibrant/glass/gradient в `HeaderNew.tsx:92–144`.

#### 3.4.2 Навигация и оболочка

Общий каркас есть и он хорош: `AppShell + HeaderNew + Sidebar` с per-route chrome из `ROUTE_REGISTRY` (1 430 строк, 71 маршрут: группы/shell/lifecycle уже размечены — готовая система координат для миграции). Но поверх: DoctorPanel дублирует сайдбар своими 6 inline-табами; у cashier/lab/registrar/landing/displayboard свои шапки; навигационные модели смешаны (`path`-based у registrar/cashier/admin vs `?tab=` у doctor/lab/специалистов); вкладки Settings не синхронизированы с URL (F5 сбрасывает); `PublicApp.tsx` — второй вход с собственными провайдерами (не монтируется).

#### 3.4.3 UX-паттерны

| Паттерн | Состояние |
|---|---|
| Тосты | **2 системы**: react-toastify (47 файлов напрямую + 46 через `services/notify.ts` — фактически стандарт) и кастомный `ToastProvider` (потребитель 1 — ChatWindow; при этом сам Toast.tsx сломан из-за мёртвых `--color-*`) |
| Подтверждения | `useConfirm` в ≥37 файлах — стандарт; остатки нативного `confirm()` — `useNavigationGuard.ts:104,126`, `pwa.ts:51`, `PaymentTest.tsx:265` |
| Лоадеры | 6 систем (см. §3.2.2); текст «Загрузка…» захардкожен в 46 TSX (61 вхождение), локализован только местами |
| Empty-state | 5+ API; часть — «false-empty» (пустые `<td colspan>` вместо честного состояния — находка UX_REMEDIATION_PLAN, не починено) |
| Ошибки API | тосты (cashier/registrar/admin) ≠ inline-баннеры (Lab) ≠ AppState-блоки (Doctor) |

#### 3.4.4 i18n

- 5 локалей (`ru.ts` — 10 363 строки); `t()` в 100+ файлах (~700 call-sites) — базовое покрытие есть.
- **Сайдбар всегда русский**: `routing/routeRegistry.ts` — 61 `label: '…'` без i18n (0 импортов `useTranslation`) + ~65 русских label в TS-конфигах (queueStatusConfig, labStatusConfig, routes…).
- Конвенции ключей разные на каждую страницу: `doctor.*`, `cashier.*`, `derma.*` (81), `dental.dental_*`, `cardio.*` (122), `registrarPanel.*|registrar.*` (105), транслит `misc.lp_* / misc.qj_*`, `legacy.*`, camelCase в TG-Shell — «отпечатки» разных агентов.
- 63 захардкоженных JSX-текста + 66 атрибутов.

#### 3.4.5 Доступность

- Сильное: **1 626 aria-вхождений в 255 файлах**, tablist-паттерны с клавиатурной навигацией (LabPanel, PatientPanel), skip-links.
- Слабое: глобальный `accessibility.css` (focus-visible, 44px touch, sr-only, reduced-motion, forced-colors) **не импортируется** — выключен; `utils/a11y.ts` — 0 потребителей; контраст-логика `colorUtils.ensureMinContrast` не вызывается из UI; 3 разные реализации skip-link.

#### 3.4.6 Responsive и состояние

- `responsive.css` подключают только 2 lazy-страницы; `hooks/useMediaQuery.ts` мёртв (0), параллельно живёт `useEnhancedMediaQuery.ts` с другими брейкпоинтами; inline isMobile-ветвления в панелях; 19 разных брейкпоинтов в CSS.
- Состояние: 8 контекстов + кастомный auth-store + emrReducer, без Zustand/Redux/ReactQuery — не блокирует UI-унификацию, но мешает консистентности состояний загрузки/ошибок.

---

### 3.5 Документальный долг (субаудит E)

**91 MD-файл / 26 207 строк / ~110 000 слов** об истории миграций. Фактически проект документировался отчётами агентов лучше, чем чинился. Ключевые проблемы:

- **Доки-призраки не архивированы**: кластер «MUI v5 Enterprise» (`MIGRATION_STRATEGY/ROADMAP/PILOT_*`, 28.02.2026 — «600+ компонентов за 4 недели, риск LOW») и кластер «Unified v2.0» (`DESIGN_SYSTEM.md`-часть, `TRANSFORMATIONS.md`, `README_DESIGN_SYSTEM.md`) описывают целевые системы, которых не существует (`unifiedTheme.js` — «never implemented as written», признание в `MIGRATION_PLAN.md`). Только MUI-кластер получил archive-notice 20.05.2026.
- **Самопротиворечия**: `DESIGN_SYSTEM.md` в одном файле: «удалить `/design-system/tokens.css` как OLD» (стр. ~807) vs «tokens.css is CANONICAL — do NOT delete (PR-UI-02)» (стр. 810). `MACOS_UI_COMPLETION_REPORT.md` («production-ready») vs `MACOS_UI_COMPLETENESS_ANALYSIS.md` (~65% готовности: формы 20%, layout 15%, dataviz 10%).
- **Три «окончательных» primary-цвета**: `#0ea5e9` (COLOR_CONSOLIDATION_PLAN) → `#3b82f6` (DESIGN_SYSTEM v2) → `#007aff` (macOS-канон).
- Что уже задокументировано как решения и подтверждено кодом (уважать): macOS-канон (UI Layer Contract в `DESIGN_SYSTEM.md`, политика `MUI_RUNTIME_INVENTORY.md`, локальная декларация `src/pages/registrar/DESIGN_SYSTEM.md`), No-New-MUI Policy, правило «один безопасный слайс за PR», AppState-примитивы как канон состояний, запрет расширения `@ts-nocheck` (55,6% файлов — уже честно посчитано в `MIGRATION_BLOCKERS.md`).

---

## 4. Сводный реестр находок (severity)

ID фиксируются для отслеживания в PR/issue. Ссылки на секции — детализация выше.

### Critical (прод-баги, влияют на пользователей прямо сейчас)

| ID | Находка | Где | Фикс |
|---|---|---|---|
| **C-1** | Toast/Modal (глобальные провайдеры) используют `--color-*`, определённые только в неподключённом `admin-styles.css` → сломанные статусные цвета тостов и фоны модалок во всём приложении | `components/common/Toast.tsx:147–221`, `Modal.tsx:188–391`, `styles/admin-styles.css` | Перевести на `--mac-*` (или перенести `--color-*`-определения в tokens.css как алиасы) |
| **C-2** | Модалка «Осмотр» на несуществующих Tailwind-классах + `var(...)` внутри `className` + `bg-white` ломает тёмную тему | `pages/DentistPanelUnified.tsx:2172–2300` | Переписать на kit `Dialog`/`Input`/`Select` + `dental-*` утилиты |
| **C-3** | 151 токен используется, но нигде не определён (369 `var()` без fallback): `--mac-info`×34, `--mac-text-muted`×21, `--admin-fs0/mb2/col0`… — битые размеры/цвета в живых панелях | `components/admin/admin.css:10004+`, `ai/AIAnalytics.css:166`, `doctor.css`, `cardiology.css` | Доопределить ~15 самых употребимых в tokens.css, остальное вычистить |
| **C-4** | `@media (prefers-color-scheme: dark) :root` в macos.css перебивает канонический dark и навязывает тёмный фон при выборе light | `styles/macos.css:6–23` | Удалить блок; темы только через классы/`data-theme` |
| **C-5** | A11y-слой отключён: accessibility.css не импортируется (skip-link, focus-visible, 44px touch, reduced-motion) | `styles/accessibility.css` | Подключить в main.tsx после tokens.css; проверить контрасты |
| **C-6** | Сайдбар и навигация всегда на русском — 61 label без i18n | `routing/routeRegistry.ts` | i18n-ключи `nav.*` |

### High (архитектурные конфликты, усиливают все остальные проблемы)

| ID | Находка | Где | Фикс |
|---|---|---|---|
| **H-1** | 6 систем токенов, 16 конфликтующих значений, 82 имени в >1 файле | см. §3.1.1–3.1.2 | Фаза 2: SSOT = tokens.css |
| **H-2** | Инвертированный каскад: патчи раньше базы, всё держится на 357 `!important` | `main.tsx:8–13` | Переупорядочить импорты → затем распустить патчи |
| **H-3** | emr-tokens.css — dark-only палитра в безусловном `:root` | `styles/emr-tokens.css:14–55` | Выразить через `--mac-*` / обернуть в `[data-theme="dark"]` |
| **H-4** | JS-мост тем (ThemeContext пишет CSS-переменные) — второй источник правды; 3 шкалы radius/font/z в TS | `theme/ThemeContext.tsx:350–429`, `tokens.ts`, `tokens-legacy.ts` | Резолвить из `--mac-*`; legacy — deprecated |
| **H-5** | Двойная навигация DoctorPanel: sidebar + 6 inline-табов с JS-hover | `pages/DoctorPanel.tsx:442–475, 657–745` | Убрать внутренние табы (паттерн cardio/derma/dentist) |
| **H-6** | 22 модалки вне кита + Modal и Dialog в ките одновременно | см. §3.2.2 | Один компонент Dialog; миграция по одному |
| **H-7** | 2 тост-системы (сломанная кастомная + react-toastify) | `common/Toast.tsx`, `AppProviders.tsx:22` | Удалить ToastProvider, ChatWindow → notify.ts |
| **H-8** | 8–11 параллельных utility-диалектов (~5 700 строк page-CSS + admin.css 12 657) | `pages/*.css`, `components/admin/admin.css` | Один utilities.css на `--mac-*`; префиксы гасить по мере миграции |
| **H-9** | ~7 000+ строк мёртвого кода в бандле (7 страниц, ~20 компонентов, ~1 650 CSS) | списки §3.2.5, §3.3.1 | Удалить (после проверки импортёров) |
| **H-10** | Dark-тема непокрыта: 0 dark-правил в CSS главных панелей, 182 isDark-ветвления в JS, патчи по инлайн-стилям | §3.4.1 | Миграция на токены устранит потребность в патчах |
| **H-11** | Tailwind-осколки в живых страницах не рендерятся (Tailwind не установлен) | `QueueJoin.tsx:733–1496`, `DentistPanelUnified` | Вычистить; `globalStyles.css` удалить или подключить осознанно |
| **H-12** | internal-demo-роуты тянут ~3 000+ строк демо-кода в прод-бандл + семейство `medical/*` | `routeRegistry.ts:1284–1372` | Вынести за флаг сборки `VITE_ENABLE_DEMO` |

### Medium (несогласованность UX, долг поддержки)

| ID | Находка | Фикс |
|---|---|---|
| **M-1** | ≥6 реализаций табов, 4 парадигмы списка пациентов, 4+ табличных стиля, 3 слоя форм настроек, 5+ empty-state API, 6 лоадеров | Единые канонические компоненты (см. §5.2) |
| **M-2** | ~2 600 inline-стилей; топ-файлы: TwoFactorManager 67, ForgotPassword 60, DentalVisitScreen 55, AIAssistant 53, AnalyticsPage 68 | Ratchet-политика: новые запрещены, старые выносятся домен за доменом |
| **M-3** | ~692 hex в 120 TSX + ~1 127 в CSS (сверх токенов) | Замена на `var(--mac-*)`; CI-guard (готовый `scripts/no-hardcoded-colors.js`) |
| **M-4** | Коллизии keyframes (`spin`×17, `pulse`×9, `fadeIn`×8) | Префикс `mac-` / единый animations.css |
| **M-5** | 19 брейкпоинтов; 2 хука медиазапросов (1 мёртвый) с разными значениями | Шкала 640/768/1024/1280(+1536); один хук |
| **M-6** | i18n-конвенции ключей разные на каждую страницу; транслит-ключи `misc.lp_*` | Схема `<domain>.<section>.<key>`; новые ключи только по схеме |
| **M-7** | 73 нативных `<select>` при живом kit Select; `title=` вместо Tooltip (69 vs 9); эмодзи-иконки в 8 файлах | Замена на kit-компоненты |
| **M-8** | 4 role-гварда, 6 файлов 2FA, 3 PWAInstallPrompt, 2 TelegramManager (root 2 496 строк жив, telegram/741 — мёртв) | Консолидация по одному на сущность |
| **M-9** | 24 font-family + 22 font-size + 30 radius значений | Только `--mac-*`-шкалы |
| **M-10** | Settings на второй токен-системе + вкладки вне URL | Миграция на `--mac-*` + `?tab=`/path |
| **M-11** | Монолиты 6 панелей = 44% кода страниц | Декомпозиция по образцу `pages/registrar/` |
| **M-12** | e2e-скриншоты только для cashier и wizard (5 PNG) — нет baseline для визуальной регрессии | Скриншот- baseline всех ключевых страниц до миграций |

### Low (гигиена)

| ID | Находка | Фикс |
|---|---|---|
| **L-1** | Рассинхрон fallback-hex одного токена (`--mac-accent-blue` → #0ea5e9/#0f766e/#2563eb/#007aff в разных файлах) | Убрать fallback-хексы или генерировать из одного источника |
| **L-2** | 4 конкурирующих `font-family` для `html`; шрифт хардкодится inline в 5+ страницах | Только `--mac-font-family` |
| **L-3** | Дубли `.sr-only`×2, scrollbar×2, `--ui-font`×2 | По одному определению в tokens.css/base |
| **L-4** | `ToastContainer theme="colored"`, мёртвые ветки тем в HeaderNew | Чистка |
| **L-5** | `/old-login` второй вход (PublicApp не монтируется — фактически мёртв) | Удалить с/pages/Login |
| **L-6** | Доки-призраки без archive-notice | Пометить архивами, оставить один актуальный индекс |

---

## 5. Целевая архитектура

### 5.1 Решение о каноне (и почему не «нейтральный медицинский»)

**Канон: macOS UI — кит `src/components/ui/macos/` + токены `--mac-*` из `src/design-system/tokens.css`.**

Обоснование по фактам, а не по вкусу:
1. **92% всех `var()`-употреблений уже `--mac-*`** (12 257 из 13 326) — меньше всего миграционных работ.
2. **Кит реально принят**: 228 файлов-импортёров, Button в 162 файлах, Input в 135 — это уже стандарт де-факто.
3. **Решение зафиксировано трижды** в живых документах (UI Layer Contract в `DESIGN_SYSTEM.md`, политика `MUI_RUNTIME_INVENTORY.md`, локальная декларация `src/pages/registrar/DESIGN_SYSTEM.md`) — смена канона породит 4-ю волну хаоса.
4. Альтернатива («нейтральный клинический» на базе Tailwind-палитры `#0ea5e9`) потребовала бы переписать светло-тему, тени и радиусы в ~500 файлах при нулевой готовой инфраструктуре.

Палитра канона (из tokens.css): акцент `--mac-accent-blue #007aff` (hover `#0051d5`, active `#004bb5`); семантика success `#30d158` / warning `#ff9f0a` / error `#ff453a`; light: bg `#ffffff/#f8f9fa/#f1f3f4`, text `#1d1d1f/#86868b`; dark: bg `#1d1d1f/#2d2d30/#3d3d40`, text `#f5f5f7/#a1a1a6`. Типографика: `-apple-system, BlinkMacSystemFont, "SF Pro Text/Display", system-ui`; размеры 11/12/13/15/17/22/28px. Отступы — база 8px (4…64). Радиусы 4/6/8/12/full. Тени 4 уровня. Анимации 120–260ms `cubic-bezier(0.2,0.8,0.2,1)`. A11y: WCAG 2.1 AA, focus-ring 2px, touch ≥44px. Брейкпоинты: **640/768/1024/1280(+1536)**. z-index — шкала `--mac-z-*` (dropdown 1000, sticky 1100, modal 1200, toast 1400).

Легальные исключения (остаются автономными вселенными, но на токенах канона): `DisplayBoardUnified` (киоск, собственные темы — выразить `--board-*` поверх `--mac-*`), `Landing` (маркетинг, допускается собственный акцент-слой поверх канон-базы), `TelegramMiniAppPatientShell` (среда Telegram WebApp — использует канон-компоненты и токены, но автономный layout).

### 5.2 Слои целевой архитектуры

```
Слой 0. tokens.css (--mac-*)          — ЕДИНСТВЕННЫЙ источник значений (цвета/шрифты/отступы/радиусы/тени/z/брейкпоинты)
Слой 1. base.css                      — reset + html/body/font + скроллбары + .sr-only (бывший accessibility.css + чистый минимум)
Слой 2. utilities.css                 — ОДИН набор утилит (flex/spacing/typography) на --mac-*; сюда мигрируют clinic-*, admin-*, 11 page-префиксов
Слой 3. ui/macos (кит, 35 компонентов) — единственные примитивы: Button, Input, Select, Dialog, Table, MacOSTab, SegmentedControl,
                                         AppState-тройка, Skeleton, Badge, Card, Tooltip, MacOSBreadcrumb, MacOSStatCard…
Слой 4. доменные компоненты           — DoctorQueuePanel, LabWorkbench*, cashier-виджеты… (только на слоях 0–3, без собственных токенов)
Слой 5. страницы                      — только композиция слоёв 3–4; inline-стили запрещены (кроме легальных динамических значений)
Слой 6. alias-layer (ВРЕМЕННЫЙ)       --bg-primary/--color-*/--surface-* → --mac-*: существует только пока идёт миграция,
                                         удаляется по её завершении
```

Правила (закрепить в CONTRIBUTING/AGENTS.md и линтерах):
1. **Никаких новых** inline-стилей (кроме вычисляемых значений), hex-цветов, `!important`, `@keyframes` без префикса, utility-классов вне utilities.css.
2. **Никаких голых** `<button>`, `<select>`, `window.confirm/alert`, самодельных модалок/табов/таблиц — только кит.
3. Тосты — только `services/notify.ts`; подтверждения — только `useConfirm`; состояния — только AppState-тройка.
4. Темы — только классом/`data-theme` на html; JS не пишет цвета.
5. i18n — все пользовательские строки через `t()`, ключи по схеме `<domain>.<section>.<key>`.
6. Один CSS-вход: импорты только в `main.tsx` в фиксированном порядке (0→1→2→кит→страничные lazy).
7. `@ts-nocheck` не добавлять в новые/правимые файлы (сейчас 55,6% — только снижать).

### 5.3 Guardrails (защита от повторного хаоса — главное отличие от прошлых планов)

В репо **уже есть готовые, но не подключенные** скрипты: `scripts/no-hardcoded-colors.js`, `scripts/check-theme-compliance.js`, `scripts/sw07-token-unification.py`. Подключить в CI с baseline-числами из §7 и политикой ratchet (числа могут только уменьшаться). Дополнить: ESLint-правило запрета `style={{` с литеральными цветами/шрифтами; stylelint (объявления цветов только через `var()`, запрет `!important` вне whitelist); проверка «неопределённых токенов» (детект `var(--x)` без определения); расширение Playwright-скриншот-тестов на все ключевые страницы.

---

## 6. Поэтапный план исправлений (фазы 0–7)

Принципы: (а) один небольшой слайс за PR — никакого масс-рефакторинга регексом (урок «regex-migration disaster»); (б) каждая фаза имеет измеримый критерий готовности; (в) порядок фаз подобран так, чтобы фонды (токены, кит) чинились до миграции потребителей; (г) все части интерфейса покрыты: панели → админка → публичные. Оценки трудозатрат — для одного агента/разработчика.

### Фаза 0 — Baseline и защита (0,5–1 день) ← начать отсюда

| # | Задача | Файлы |
|---|---|---|
| 0.1 | Playwright-скриншоты ключевых страниц (light+dark): login, doctor, registrar, cashier, lab, patient, cardio/dentist/derma, settings, analytics, landing, queue, display-board, setup | расширить `e2e/visual-regression.spec.ts` |
| 0.2 | Подключить готовые guardrail-скрипты в CI с текущими baseline-числами (§7), политика ratchet | `scripts/no-hardcoded-colors.js`, `scripts/check-theme-compliance.js` |
| 0.3 | Зафиксировать этот документ как единственный план; пометить archive-notice доки-призраки | MUI-v5-кластер, Unified-v2.0-кластер |

**DoD:** скриншот-baseline в репо; CI падает при росте метрик; старые планы помечены.

### Фаза 1 — Хотфиксы Critical (1–2 дня)

| # | Задача | Ссылка |
|---|---|---|
| 1.1 | Починить Toast/Modal: перевести на `--mac-*` (или добавить алиасы `--color-*` в tokens.css) | C-1 |
| 1.2 | Переписать модалку «Осмотр» DentistPanelUnified на kit Dialog/Input/Select | C-2 |
| 1.3 | Доопределить в tokens.css ~15 самых употребимых недостающих токенов (`--mac-info`, `--mac-text-muted`, `--mac-font-weight-normal`, `--mac-font-size-md`, `--mac-spacing-md/sm`, `--mac-blue-500`…); списком в PR | C-3 |
| 1.4 | Удалить `@media (prefers-color-scheme: dark):root` из macos.css; темы только классом | C-4 |
| 1.5 | Подключить accessibility.css в main.tsx | C-5 |
| 1.6 | Удалить мёртвые страницы и компоненты (проверив импортёры): pages/{Activation, SecurityPage, TelegramPage, FileSystemPage, MobilePatientDashboard, Login}.tsx, PublicApp.tsx, components/{examples, test, display, forms, medical/MedicalTable, root Icon.tsx, 2×PWAInstallPrompt, root TwoFactor*}, orphan-CSS; вычистить их i18n-ключи | H-9, L-5 |

**DoD:** нет `var()` без определения в живых модулях; тосты/модалки окрашены корректно в обеих темах; `npm run build` проходит; бандл легче на ~7 000 строк.

### Фаза 2 — Единый источник токенов (3–5 дней)

| # | Задача |
|---|---|
| 2.1 | Переупорядочить импорты в main.tsx (и убрать дубль из App.tsx): `tokens.css → base(accessibility) → utilities → macos.css(каркас) → admin.css → header-new.css → патчи` — патчи после базы |
| 2.2 | tokens.css = SSOT: перенести недостающие определения; расширить до полной light/dark матрицы; зафиксировать шкалы (radius 4/6/8/12, font 11–28, z 1000–1400, брейкпоинты 640/768/1024/1280) |
| 2.3 | Создать alias-слой (временный): `--bg-primary/--text-*/--accent-color/--color-*/--surface-*` → `--mac-*` — единое место (в tokens.css или отдельный aliases.css), удалить дубль-определения из theme.css; починить конфликт `--accent-color → --mac-accent-blue vs --mac-accent` (один вариант) |
| 2.4 | emr-tokens.css выразить через `--mac-*` (убрать dark-only `:root`-палитру) |
| 2.5 | JS-токены: `theme/tokens.ts` + `tokens-legacy.ts` депрекейтнуть; ThemeContext перестаёт писать цвета — только класс темы; удалить `theme/tokens/`, `constants/a11yTokens.ts` (или свести к `--mac-*`) |
| 2.6 | Свести 19 брейкпоинтов к канон-шкале; префиксовать keyframes (`mac-spin`, `mac-fadeIn`…), убрать дубли-определения |

**DoD:** 0 неопределённых токенов; 1 файл-источник значений; тёмная/светлая тема переключается без JS-моста; скриншот-тесты зелёные.

### Фаза 3 — Унификация UX-примитивов (1–1,5 недели)

| # | Задача | Объём |
|---|---|---|
| 3.1 | Модалки: оставить в ките **только Dialog** (Modal.tsx депрекейтнуть); мигрировать 22 внешних файла по 2–3 за PR | 22 файла |
| 3.2 | Тосты: удалить ToastProvider, ChatWindow → `notify.ts` | H-7 |
| 3.3 | Слить Modern*-семейство в кит: ModernInput/Select/Textarea → Input/Select/Textarea; ModernDialog → Dialog; ModernTabs → MacOSTab/SegmentedControl; ModernCard/Grid/Flex/Container → Card/Grid/Box (ModernFilters оставить как композит) | 29 файлов |
| 3.4 | Empty/Loading/Error → только AppState-тройка (MacOSEmptyState/AnalyticsEmptyState/renderEmptyState/PanelEmptyState мигрировать) | ~60 вхождений |
| 3.5 | Таблицы: канон — kit `Table` (или Enhanced как тяжёлый вариант до поры); мигрировать cashier-table ×4, QueueTable, RefundRequestsTable; убрать чекбокс-переключатель в Appointments | 6+ таблиц |
| 3.6 | Confirm: заменить 4 остатка нативного confirm/alert; role-гварды → один RoleGate | M-8 |
| 3.7 | Иконки: lucide-react как стандарт; root Icon.tsx удалить; эмодзи-иконки заменить | 8 файлов |

**DoD:** по каждому примитиву ровно одна реализация; grep-проверки в CI (`*Modal*.tsx` вне кита = 0 и т.п.).

### Фаза 4 — Оболочка и навигация (3–5 дней)

| # | Задача |
|---|---|
| 4.1 | DoctorPanel: удалить дублирующие inline-табы + JS-hover (H-5), перейти на sidebar `?tab=` как cardio/derma/dentist |
| 4.2 | Табы всех панелей → MacOSTab/SegmentedControl (Analytics, Settings — вкладки в URL, Lab — сохранить a11y-паттерн, перенеся на kit) |
| 4.3 | Сайдбар: i18n routeRegistry (61 label → ключи `nav.*`) (C-6); выровнять навигационные модели (решение: `path`-based, как registrar) |
| 4.4 | Вынести internal-demo за флаг `VITE_ENABLE_DEMO` (H-12); HeaderNew: удалить мёртвые ветки тем |

**DoD:** одна модель навигации; 0 русских label в routeRegistry; демо-код вне прод-бандла.

### Фаза 5 — Миграция доменов (3–4 недели, по 1 панели/PR)

Порядок = комбинация «грязь × пользовательская ценность» (все части важны — порядок оптимизирует выигрыш, а не важность):

| Волна | Домен/страница | Работы |
|---|---|---|
| 5.1 | **dermatology** (268 inline) → **doctor** (95, включая DoctorPanel-остатки) | inline → классы/токены; raw-таблица пациентов → канон Table |
| 5.2 | **cardiology** (103) → **dental** (90 + хвосты C-2) | то же; derma-карточки пациентов → канон EmptyState/Table |
| 5.3 | **admin** (172 inline / 40 файлов; admin.css 12 657 строк) | вынос utility в utilities.css, гашение `admin-*`-диалекта, 27 файлов с голыми button → kit Button; Analytics → MacOSStatCard + SegmentedControl |
| 5.4 | **emr-v2** (67 inline + 24 CSS) | CSS на `--mac-*`, TreatmentSection −22 hex |
| 5.5 | **auth/файловые** (TwoFactorManager 67, ForgotPassword 60, AIAssistant 53, FileManager 51, LoginFormStyled 52 hex) | inline → токены; LoginForm на kit Input/Button |
| 5.6 | **Settings** (legacy-токены → `--mac-*`), **Search/UserProfile** (стили-объекты → CSS), **QueueJoin** (хвосты Tailwind, 77 inline), **PaymentSuccess/Cancel** | по странице за PR |
| 5.7 | **Landing/DisplayBoard/TG-Shell** (легальные исключения) | выразить локальные токены поверх `--mac-*`; TG-Shell декомпозиция |

**DoD каждой волны:** 0 новых inline/hex; скриншот-тесты; домен-CSS ≤ 300 строк утилит (остальное — kit).

### Фаза 6 — Декомпозиция монолитов (параллельно фазе 5, отдельные PR)

Топ-6 монолитов (13 127 строк) разбить по образцу `pages/registrar/` (панель-обёртка + hooks + view-компоненты): Dentist 2 419 → TG-Shell 2 328 → Registrar 2 240 → Cashier 2 125 → Cardio 2 054 → Derma 1 961. Каждый — серия PR «извлечь один view/хук», без изменения поведения.

### Фаза 7 — Распущение патчей и финальная гигиена (3–5 дней)

| # | Задача |
|---|---|
| 7.1 | По мере роста adoption распустить патч-слои: `global-fixes.css`, `dark-theme-visibility-fix.css`, `[style*=]`-блоки macos.css — каждый блок удаляется только когда покрываемые inline-стили устранены |
| 7.2 | Удалить alias-слой (слой 6) — финальный признак завершения миграции |
| 7.3 | Удалить cursor-effects.css, admin-styles.css (после C-1), theme/tokens/; свести дубли .sr-only/scrollbar/--ui-font |
| 7.4 | Итог: один CSS-вход в main.tsx; stylelint+eslint правила активны в строгом режиме; обновить §7-метрики |
| 7.5 | Обновить AGENTS.md/CLAUDE.md: правила §5.2 + ссылка на этот план как единственный |

**DoD:** 0 «спасательных» селекторов; alias-слой удалён; метрики §7 достигнуты.

---

## 7. Метрики успеха (текущее → цель)

| Метрика | Текущее | Цель после Фазы 7 | Проверка |
|---|---|---|---|
| Систем токенов | 6 | **1** (+alias-слой удалён) | ручной инвентарь + CI-скрипт |
| `var()` без определения | 151 имя / 369 вызовов | **0** | `scripts/sw07-token-unification.py` / свой детектор |
| Primary-цвета | 6 hex | **1** (`#007aff`) | `no-hardcoded-colors.js` |
| Hex в TSX | ~692 / 120 файлов | **≤ 30** (только вычисляемые) | CI |
| Hex в CSS вне tokens.css | ~1 127 | **0** | CI |
| Inline `style={{}}` | ~2 600 / ~240 файлов | **≤ 300** (динамические значения) | ESLint + счётчик |
| `!important` | 357 CSS + 80 TSX | **≤ 30** (whitelist) | stylelint |
| Модальные системы | 22 файла + 2 в ките | **1** (Dialog) | grep-гвард |
| Таб-системы | ≥6 | **1** (MacOSTab/SegmentedControl) | grep-гвард |
| Toast-системы | 2 | **1** (notify.ts) | grep-гвард |
| Empty-state API | 5+ | **1** (AppState) | grep-гвард |
| Брейкпоинты | 19 | **4–5** | stylelint |
| keyframes-дубли | spin×17, pulse×9… | **0** (префикс mac-) | CI |
| Мёртвые страницы/компоненты | ~27 единиц / ~7 000+ строк | **0** | dead-code анализ |
| Русские label в routeRegistry | 61 | **0** | grep |
| Dark-патчи по инлайн-стилям | 53 селектора + 78 !important в macos.css | **0** | удалённые файлы |
| `@ts-nocheck` | 55,6% | не растёт, −10 п.п. | счётчик |
| A11y CSS подключён | нет | да + контраст-проверка | CI/чек-лист |

Ratchet: каждое значение фиксируется в CI после Фазы 0 и может только уменьшаться.

---

## 8. Риски и правила безопасности миграции

| Риск | Мера |
|---|---|
| Повторение «regex-migration disaster» (уже было: фазы 2–9 ломали деструктуризацию) | Один файл/компонент за PR; никаких глобальных find-replace; ручная проверка diff |
| Визуальные регрессии в живых панелях | Скриншот-baseline Фазы 0; каждый миграционный PR прикладывает скриншоты до/после |
| Скрытые зависимости мёртвых файлов (i18n-ключи, тесты, re-export) | Перед удалением: grep импортёров + ключей + прогон тестов; удаление отдельным PR |
| Активная разработка параллельно миграции | Мигрировать файлы только когда они не в активной работе; правила §5.2 в AGENTS.md остановят рост хаоса уже сейчас |
| Каскадные сюрпризы при переупорядочивании CSS | Фаза 2.1 — отдельный PR со скриншот-прогоном всех ключевых страниц |
| Расползание сроков | Фазы 1–4 — быстрый выигрыш (≈2–3 недели суммарно); Фазы 5–6 можно останавливать/продолжать без потери целостности |
| @ts-nocheck скрывает типологические ошибки при миграции | Не снимать nocheck в миграционных PR (отдельная очередь); новые файлы — строго с типами |

---

## 9. Приложения

### 9.1 Карта «старое → новое»

| Сейчас | Канон |
|---|---|
| `--bg-primary/--text-primary/--accent-color/--hover-bg` (theme.css) | alias → `--mac-bg-primary/--mac-text-primary/--mac-accent-blue/--mac-bg-hover` |
| `--color-success/danger/warning/info` (мёртвый admin-styles.css) | `--mac-success/--mac-error/--mac-warning/--mac-info` |
| `--surface-*/--space-*/--radius-*` (emr-tokens.css) | `--mac-bg-*/--mac-spacing-*/--mac-radius-*` |
| `theme/tokens.ts` / `tokens-legacy.ts` (JS-палитры) | удалить; чтение из CSS-токенов |
| `<button className="admin-*/doctor-*/…-btn">`, голые `<button>` | kit `Button` (+variant) |
| Modern*/Responsive* / bespoke-модалки (22 файла) | kit `Dialog` |
| cashier-table / QueueTable / RefundRequestsTable / raw `<table>` | kit `Table` (тяжёлые случаи — Enhanced*) |
| ModernTabs / рукописные табы / TabButton / Button-ряды | `MacOSTab` / `SegmentedControl` (сохранив a11y-паттерн Lab) |
| ToastProvider / toast() прямые вызовы | `services/notify.ts` |
| confirm()/alert() остатки | `useConfirm` |
| MacOSEmptyState/StateWrapper/PanelEmptyState/`<td colspan>` | `AppState.AppEmpty/AppLoading/AppError` |
| AnimatedLoader/спиннеры/«Загрузка…» | `AppState.AppLoading` / `Skeleton` |
| lucide + root Icon.tsx + эмодзи | только lucide-react |
| `title="…"` | kit `Tooltip` |
| нативный `<select>` | kit `Select` |
| RoleGate/RoleGuard/ProtectedRoute/RequireAuth | один `RoleGate` |
| 2FA ×6 файлов | `security/TwoFactorManager` + wizard |
| `clinic-*`/`admin-*`/11 page-префиксов утилит | единый `utilities.css` |

### 9.2 Готовые инструменты в репо (подключить в Фазе 0)

- `frontend/scripts/no-hardcoded-colors.js` — детект hex вне токенов
- `frontend/scripts/check-theme-compliance.js` — проверка тем
- `frontend/scripts/sw07-token-unification.py` — унификация токенов
- `frontend/e2e/visual-regression.spec.ts` + snapshots (расширить с 5 PNG на все ключевые страницы)
- guardrail-тесты в `src/__tests__/` (уже следят за отдельными паттернами — дополнить гардами §3/grep-правилами)

### 9.3 Эталоны для копирования

- Декомпозиция панели: `pages/registrar/` (+`registrar.css:14–29` deprecation-нотис как образец коммуникации)
- A11y-табы: `LabPanel.tsx:586–616`, `PatientPanel` (`pp-tablist`)
- CSS на токенах: `Setup.css`
- Sidebar-модель: `routeRegistry.ts` (path-based, preset'ы)

### 9.4 Что НЕ делать (исторические уроки)

1. Не вводить новые дизайн-системы, UI-библиотеки (MUI и пр.) или «универсальные темы» — уже 3 раза приводило к новой волне хаоса.
2. Не верить отчётам о «100% завершено» без grep-проверки.
3. Не мигрировать регексом по многим файлам.
4. Не чинить dark-тому новыми патч-файлами — только устранением причин (inline-стили, хардкод).
5. Не добавлять новые utility-префиксы доменов — только utilities.css.


