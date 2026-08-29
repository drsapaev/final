# UI Remediation Plan — Clinic Management Frontend

> **Документ-источник правды для миграции UI репозитория `drsapaev/final`.**
> Сопровождается жёстким контрактом `AGENTS_UI.md` — прочитать ПЕРЕД началом работы.

**Версия:** 1.9 · **Дата:** 29.08.2026 · **Основано на:** UI-аудите от 18.08.2026 + cross-check с актуальным main от 21.08.2026; статусы PR синхронизированы с main `64f73d40` (progress snapshot — исполнение правила №7 AGENTS_UI); Phase 2C info-family definition-only remediation VERIFIED на `e16f3b0c`; Phase 2A `--mac-text-muted` consumer migration VERIFIED на `9b1ef5d`; Phase 2B-A `--mac-spacing-md` single-usage remediation VERIFIED на `26410a025`; PR-UI-09a DataTable foundation remediation MERGED-VERIFIED на `8143a361`; PR-UI-09b decommission dead Table implementations MERGED-VERIFIED на `11b423990`; PR-UI-09c live-consumer migration COMPLETE — 4 инкремента (#2857 → `c8464c81`, #2860 → `e35df1f0`, #2861 → `e17d261b`, #2862 → `028ab397`) MERGED-VERIFIED; PR-UI-09d final alias-cleanup MERGED-VERIFIED на `7243a108` (#2870); PR-UI-09e-1 DataTable row virtualization (AC4) MERGED-VERIFIED на `d20cde25` (#2872); PR-UI-10 branding MERGED-VERIFIED на `865ab5d8` (#2867, + follow-up #2869 → `66c7ceff`); PR-UI-11-1 AdminDashboard data-first + canonical DataCard MERGED-VERIFIED на `1378d6ef` (#2871); PR-UI-11-2 admin MacOSCard consumers → canonical Card MERGED-VERIFIED на `32edbc20` (#2873); PR-UI-11-3..11-12 MacOSCard-миграция (10 инкрементов #2876/#2878/#2880/#2882/#2884/#2886/#2888/#2889/#2892/#2894) MERGED-VERIFIED; PR-UI-19 Navigation i18n (C-6) MERGED-VERIFIED на `faace538` (#2879); PR-UI-12 EMR+Queue+Table UX COMPLETE — 4 инкремента (12-1 #2885 → `4199b9c2`, 12-2 #2890 → `f4d577d7`, 12-3 #2891 → `26347af3`, 12-4 #2893 → `64f73d40`) MERGED-VERIFIED.

---

## Содержание

1. [Контекст и диагноз](#1-контекст-и-диагноз)
2. [Целевая архитектура](#2-целевая-архитектура)
3. [File-level матрица решений](#3-file-level-матрица-решений)
4. [Sprint Plan — 19 PR за 6 спринтов](#4-sprint-plan--19-pr-за-6-спринтов)
5. [P0: критические дефекты (4 PR)](#5-p0-критические-дефекты-4-pr)
6. [P1: primitives & state patterns (5 PR)](#6-p1-primitives--state-patterns-5-pr)
7. [P2: migration & branding (6 PR)](#7-p2-migration--branding-6-pr)
8. [P3: landing & polish (3 PR)](#8-p3-landing--polish-3-pr)
9. [Regression strategy](#9-regression-strategy)
10. [Risk matrix](#10-risk-matrix)

---

## 1. Контекст и диагноз

### 1.1. Что подтвердил cross-check с актуальным main

UI-аудит от 18.08.2026 был выполнен на снапшоте репозитория. Cross-check с актуальным main от 21.08.2026 (коммит `2a7487e`) подтвердил большинство находок, но часть уже изменилась:

| Находка аудита (18.08) | Состояние в main (21.08) | Действие |
|---|---|---|
| `LanguageSwitcher.tsx` использует локальный `useState('en')` + toggle без i18next | **ИСПРАВЛЕНО** в `LanguageSwitcher.tsx` — теперь использует `useTranslation().setLanguage(code)` | Удалить из плана; оставить regression-тест |
| `UnifiedSidebar.tsx` содержит тот же баг (строки 31, 74) | **ПОДТВЕРЖДЕНО** — баг живёт в `UnifiedSidebar.tsx:31,74` | PR-UI-03: удалить `UnifiedSidebar` целиком (используется только в `MediLabDemo`) |
| 5 параллельных UI-слоёв (macOS, Modern*, MUI, Tailwind, Unified*) | **ПОДТВЕРЖДЕНО** — все слои присутствуют | PR-UI-05..07: унификация |
| Два ThemeProvider (ThemeContext + MacOSThemeProvider) | **ПОДТВЕРЖДЕНО** — `ThemeContext.tsx` (661 LOC) + `macosTheme.tsx` (177 LOC) параллельно | PR-UI-01: слить в один |
| 6 color schemes (light/dark/auto + vibrant/glass/gradient) | **ПОДТВЕРЖДЕНО** — `colorScheme.ts:264` `COLOR_SCHEMES` | PR-UI-01: vibrant/glass/gradient → feature-flag |
| 8 Card-типов (ModernCard, MacOSCard, UnifiedCard, MetricCard, MedicalCard, PatientCard, StatCard, DataCard) | **ПОДТВЕРЖДЕНО** — все 8 присутствуют, разбросаны по 69 файлам | PR-UI-06: 3 типа (Card / StatCard / DataCard) |
| 6 Table-реализаций (EnhancedAppointmentsTable, common/Table, macos/Table, ResponsiveTable, RefundRequestsTable, QueueTable) | **ПОДТВЕРЖДЕНО** — 4 496 LOC суммарно, EnhancedAppointmentsTable — god-компонент 2 279 LOC | PR-UI-09: canonical DataTable |
| 3 модели навигации (sidebar для admin, header-tabs для registrar, ModernTabs в теле страницы для doctor/lab) | **ПОДТВЕРЖДЕНО** — `SIDEBAR_PRESETS` (строки 33-100 routeRegistry.ts) активны только для admin/doctor/lab/cardio/derma/dentist; registrar/cashier/patient — закомментированы (P-016) с пометкой «navigation lives in HeaderNew» | PR-UI-04: единый AppShell |
| `BRAND.logo = '/brand/logo.svg'` указывает на несуществующий `public/brand/` | **ПОДТВЕРЖДЕНО** — `public/brand/` не существует, файл `brand.ts` ссылается на несуществующие assets | PR-UI-10: создать brand assets |
| Двойное имя продукта "MediClinic Pro" + "Clinic OS" в landingContent | **ПОДТВЕРЖДЕНО** — 36 упоминаний обоих имён в `landingContent.ts` | PR-UI-10: унифицировать на "Clinic OS" |
| `cursor-effects.css` (520 LOC) + `sidebar-buttons.css` (75 LOC) — мёртвый CSS | **ПОДТВЕРЖДЕНО** — импортируются только в `MediLabDemo.tsx` и `UnifiedSidebar.tsx` (оба — demo-only) | PR-UI-17: удалить оба файла |
| `components/medical/` (4 файла, 1 097 LOC) — мёртвый код | **ПОДТВЕРЖДЕНО** — `MedicalCard` импортируется только в `MediLabDemo.tsx:10` | PR-UI-17: удалить каталог |
| `forms/Modern*` (4 файла, 705 LOC) — мёртвый код | **ПОДТВЕРЖДЕНО** — 0 импортов во всём `src/` | PR-UI-17: удалить каталог |

### 1.2. Главный диагноз

**Проблема интерфейса — архитектурная, не косметическая.** Функционально система зрелая (18 ADR, 314 unit-тестов, 71 маршрут, WebSocket real-time, mutation testing), но UI не имеет одного визуального языка. Это проявляется в:

- **5 параллельных UI-слоёв** в одной кодовой базе
- **2 ThemeProvider**, которые слушают события друг друга через `window.dispatchEvent('colorSchemeChanged')` (см. `ThemeContext.tsx:333` + `macosTheme.tsx:86`)
- **2 accent-blue** переменных (`--mac-accent-blue` в macos-tokens.css + `--accent` в macosTheme.tsx, которые перезаписывают друг друга)
- **6 цветовых схем** с комбинаторным взрывом тестирования (6 тем × 12 surfaces × 4 состояния ≈ 288 комбинаций)
- **3 модели навигации** (sidebar для админа, header-tabs для регистратора, ModernTabs в теле страницы для врача) — пользователь с правами Admin+Registrar видит разные UX на двух экранах

### 1.3. Выбранное направление: B — Medical Minimalism

Из трёх вариантов:

- **A. macOS UI** (текущий primary layer) — привлекательный, но «десктоп-приложение», а не «клиническая система»
- **B. Medical Minimalism** ✅ — белая/светлая основа, спокойный медицинский teal, сильная типографическая иерархия, плотные таблицы, data-first
- **C. Полный редизайн** — неприемлемо: создаст 6-й слой поверх существующих 5

Выбран **B**, с сохранением лучших interaction-patterns из macOS (spacing scale, focus-ring, keyboard shortcuts, `:focus-visible`, reduced-motion). Это не косметика, а **Layout Restructure**: один source of truth на каждом слое.

**Ключевая метрика успеха:** пользователь с любой ролью (Admin, Registrar, Doctor, Cashier, Lab, cardio/derma/dentist) видит один и тот же AppShell, одни и те же primitives, одну и ту же модель навигации. Различаются только accent color и набор пунктов в sidebar.

---

## 2. Целевая архитектура

![Целевая архитектура Clinic OS UI](./assets/target_arch.png)

### 2.1. 5 слоёв сверху вниз

| Слой | Файлы (canonical) | Что включает | Что НЕ включает |
|---|---|---|---|
| **Foundation** | `src/design-system/tokens.css` · `src/contexts/ThemeContext.tsx` · `src/i18n/useTranslation.ts` | CSS-переменные (light/dark + auto), ThemeProvider (single), i18next integration | MacOSThemeProvider, colorScheme.ts custom schemes, accent-picker |

**Theme type contract (уточнение из §2 AGENTS_UI):**
```ts
type Theme = 'light' | 'dark' | 'auto';            // что выбрал пользователь
type ResolvedTheme = 'light' | 'dark';              // что фактически применилось

interface ThemeContextValue {
  theme: Theme;                                     // хранится в localStorage 'colorScheme'
  resolvedTheme: ResolvedTheme;                     // вычисляется из theme + prefers-color-scheme
  setTheme: (t: Theme) => void;
  toggleTheme: () => void;                          // cycling: light → dark → auto → light
}
```

Компоненты читают **только `resolvedTheme`** — они не знают, пришла ли тема из `light`/`dark`/`auto`. Это убирает dual-truth: `--mac-bg-primary` всегда соответствует `resolvedTheme`, без задержки на `window.dispatchEvent('colorSchemeChanged')`.
| **App Shell** | `src/App.tsx` (AppShell) · `src/components/layout/HeaderNew.tsx` · `src/components/ui/macos/Sidebar.tsx` | Header (brand + search + notifications + profile + lang + theme) + Sidebar (RBAC-driven) + Main content | UnifiedSidebar, UnifiedLayout, Nav, ModernTabs-as-nav |
| **Routing & RBAC** | `src/routing/routeRegistry.ts` · `src/routing/routeGuards.tsx` · `src/routing/routeSelectors.ts` | 71 маршрут с id/path/roles/shell/component, SIDEBAR_PRESETS, route guards, 401/403/404 | — |
| **UI Primitives** | `src/components/ui/Button.tsx` · `Card.tsx` · `DataTable.tsx` · `Modal.tsx` · `AppState.tsx` · `Form.tsx` | Button (6 variants), Card/StatCard/DataCard (3 типа), DataTable (sticky/sort/filter/pagination), Modal (focus trap), AppState (loading/empty/error unified) | ModernCard, MacOSCard, UnifiedCard, MetricCard, MedicalCard, PatientCard, ModernDialog, ModernInput, ModernSelect, ModernTextarea, ModernForm, AppEmpty, MacOSEmptyState, ResponsiveTable, common/Table |
| **Pages & Role Panels** | `src/pages/*.tsx` (12 panels) | Admin (38 экранов), Registrar, Doctor, Cashier, Lab, cardio/derma/dentist, Patient | — |

### 2.2. Принцип «одного источника правды»

Каждый визуальный аспект имеет один canonical-источник:

| Аспект | Canonical | Альтернативы (после миграции) |
|---|---|---|
| CSS-переменные | `tokens.css` | — |
| Theme state | `useTheme()` из ThemeContext — `theme: 'light' \| 'dark' \| 'auto'` + `resolvedTheme: 'light' \| 'dark'` | — |
| Language state | `useTranslation().language` из i18next | — |
| Accent color | `--mac-accent` (один, медицинский teal) | role-tinted только в sidebar active item |
| Sidebar items | `SIDEBAR_PRESETS[role]` в routeRegistry | — |
| Icon library | `lucide-react` (прямые импорты) | — |
| Spacing | `--mac-spacing-1..16` (4px grid) | — |
| Typography | `--mac-font-size-xs..3xl` (7 размеров) | — |
| Card component | `Card` / `StatCard` / `DataCard` | — |
| Table component | `DataTable` | — |
| Empty/loading/error | `AppState` (AppLoading + AppEmpty + AppError) | — |

---

## 3. File-level матрица решений

### 3.1. Theme & design tokens

| Файл | LOC | Действие | Причина | PR |
|---|---|---|---|---|
| `src/contexts/ThemeContext.tsx` | 661 | **MIGRATE** | Оставить как canonical ThemeProvider. Удалить логику синхронизации с MacOSThemeProvider (строки 333-336 dispatch `colorSchemeChanged`). Упростить: только `theme: 'light'\|'dark'`, `setTheme(t)`, `toggleTheme()`. Remote sync с `/users/me/preferences` оставить. | PR-UI-01 |
| `src/theme/macosTheme.tsx` | 177 | **DELETE** ✅ #2812 | Дублирует ThemeProvider. Accent-picker (8 accent names) — удалить; `--mac-accent-blue` canonical в tokens.css. `useMacOSTheme` используется только в `AccentPicker.tsx` и `ColorSchemeSelector.tsx` — оба мигрировать. | PR-UI-01 ✅ |
| `src/theme/colorScheme.ts` | 450 | **MIGRATE** ✅ #2814 | Удалить определения `vibrant`, `glass`, `gradient` из `COLOR_SCHEME_DEFINITIONS` (строки 102, 153, 214). Оставить только `light`, `dark`, `auto`. Функции `applyColorSchemeToDom`, `persistColorSchemeLocally`, `resolveThemeMode` — оставить. Выполнено + добавлена migration-логика (normalizeColorScheme для legacy-значений). | PR-UI-01 ✅ |
| `src/theme/macos-tokens.css` | 677 | **MIGRATE** ✅ #2814 → `src/design-system/tokens.css` | Переименовать + убрать `[data-color-scheme="vibrant"]`, `[data-color-scheme="glass"]`, `[data-color-scheme="gradient"]` секции (строки 25-95 в `styles/macos.css`). Light/Dark только. **PR-08 (#2838, 25.08.2026) D4 primitives:** +54 LOC canonical entrance-семейство добавлено в `tokens.css` (4 `@keyframes` mac-entrance-up/left/right/scale + 4 utility classes `.mac-entrance-up/left/right` 0.6s ease-out + `.mac-entrance-scale` 0.4s ease-out + 5 `.mac-delay-100..500` + reduced-motion block update). Values byte-identical legacy `fadeInUp/Left/Right/Scale` (equivalence-by-construction); 15 MediLabDemo legacy refs migrated. | PR-UI-02 ✅ (+ PR-UI-08 D4) |
| `src/theme/tokens-legacy.ts` | — | **DELETE** ⬜ | Используется только в ThemeContext.getColor/getSpacing. После миграции ThemeContext на прямое чтение CSS-переменных — удалить. **Ownership-фикс (25.08.2026):** удаление перенесено из PR-UI-02 в PR-UI-17 — файл жив, единственный импортёр `ThemeContext.tsx`. | PR-UI-02 → **PR-UI-17** |
| `src/theme/colorUtils.ts` | — | **KEEP** | Утилиты `mixColors`, `toRgbaString` используются в ThemeContext. Оставить как есть. | — |
| `src/styles/macos.css` | 840 | **MIGRATE** ✅ #2814 (частично) | Удалить секции vibrant/glass/gradient (строки 25-95, ~70 LOC) — выполнено (~259 LOC удалено). Оставить остальное. После PR-UI-02 переименовать в `design-system/styles.css`. **UI-audit track C-4 (commit `c9ea39edd`, 25.08.2026, ОТДЕЛЬНЫЙ pre-PR-08 commit, НЕ часть PR-UI-08):** дополнительная очистка — `@media (prefers-color-scheme: dark) :root` block (5 legacy vars: `--bg`/`--text`/`--surface`/`--glass-stroke`/`--shadow`) + dead `.glass` rule (last consumer of legacy vars) removed; canonical `--mac-bg-primary` replacement for `html { background-color }`. C-4 attributed to UI-audit track, не к PR-UI-08. | PR-UI-02 ✅ (+ C-4 follow-up) |
| `src/styles/theme.css` | 578 | **MIGRATE** | Аудит и консолидация с `tokens.css`. Дублирующие `:root`-определения — удалить. | PR-UI-02 |
| `src/styles/dark-theme-visibility-fix.css` | 164 | **KEEP** | Полезные dark-mode патчи. Оставить. | — |
| `src/styles/global-fixes.css` | 232 | **KEEP** | Полезные global fixes. Оставить. | — |

### 3.2. App Shell & navigation

| Файл | LOC | Действие | Причина | PR |
|---|---|---|---|---|
| `src/App.tsx` | 494 | **MIGRATE** | AppShell — упростить. Удалить двойную логику compact-sidebar для mobile (строки 246-322). Использовать стандартный overlay-drawer pattern. | PR-UI-04 |
| `src/components/layout/HeaderNew.tsx` | 705 | **MIGRATE** | Удалить хардкод navigational buttons для registrar/cashier (после PR-UI-04 они не нужны). Сократить до ~300 LOC. Оставить: brand, GlobalSearchBar, NotificationCenter, profile menu, LanguageSwitcher, theme toggle. | PR-UI-04 |
| `src/components/ui/macos/Sidebar.tsx` | 649 | **MIGRATE** | Оставить как canonical sidebar. Удалить эффекты (text-shadow, transform, backdrop-filter) из активного пункта. Hover = background tint + font-weight emphasis только. | PR-UI-04 |
| `src/components/layout/UnifiedSidebar.tsx` | 498 | **DELETE** ✅ #2810 | Используется только в `MediLabDemo.tsx` (demo-only). Содержит 5 проблем: локальный `useState('en')` (строка 31), toggle без i18next (строка 74), 5 event-listeners для color scheme sync (строки 33-64), `auth.clearToken()` без redirect (строка 482), визуальные эффекты (text-shadow, box-shadow, transform, backdrop-filter). Все проблемы ушли с удалением файла. | PR-UI-03 ✅ |
| `src/components/layout/UnifiedLayout.tsx` | 123 | **DELETE** ✅ #2810 | Используется только в `MediLabDemo.tsx`. После удаления UnifiedSidebar — не нужен. **Ownership-фикс (25.08.2026):** фактически удалён в PR-UI-03 (раньше плана — матрица относила к PR-17). | PR-UI-17 → **PR-UI-03** (факт) |
| `src/components/layout/Nav.tsx` | 102 | **DELETE** | Используется только в `Activation.tsx` (онбординг). Мигрировать Activation на AppShell, удалить Nav. | PR-UI-17 |
| `src/components/layout/ModernCard.tsx` | 176 | **DELETE** ✅ #2820 | 0 импортов в `src/`. Мёртвый код. | PR-UI-06 ✅ |
| `src/components/layout/ModernContainer.tsx` | 76 | **DELETE** | 0 импортов. Мёртвый код. | PR-UI-17 |
| `src/components/layout/ModernFlex.tsx` | 93 | **DELETE** | 0 импортов. Мёртвый код. | PR-UI-17 |
| `src/components/layout/ModernGrid.tsx` | 105 | **DELETE** | 0 импортов. Мёртвый код. | PR-UI-17 |
| `src/components/navigation/ModernTabs.tsx` | — | **MIGRATE** ⬜ | Используется как content-tabs (внутри страниц), НЕ как навигация (33 потребителя). Оставить, но переименовать в `Tabs.tsx` для ясности. **Ownership-фикс (25.08.2026):** rename отложен из PR-UI-04 в PR-UI-17. | PR-UI-04 → **PR-UI-17** |
| `src/pages/MediLabDemo.tsx` | 779 | **MIGRATE** | Демо-страница (доступна только Admin при `VITE_ENABLE_INTERNAL_DEMO=1`). После удаления UnifiedLayout — мигрировать на AppShell с пометкой `data-demo="true"`. Альтернативно: удалить полностью, если демо не нужно. | PR-UI-17 |
| `src/pages/MacOSDemoPage.tsx` | 19 | **KEEP** | Минимальная демо-страница. Оставить. | — |

### 3.3. Icon system

| Файл | LOC | Действие | Причина | PR |
|---|---|---|---|---|
| `src/components/Icon.tsx` | 60 | **DELETE** | Legacy icon component с `assets/iconsMap`. Используется в 5 местах: `MediLabDemo.tsx`, `UnifiedSidebar.tsx`, `medical/MedicalTable.tsx`, `medical/PatientCard.tsx`, `medical/MetricCard.tsx`. Все эти файлы удаляются в PR-UI-03/17. | PR-UI-17 |
| `src/components/ui/macos/Icon.tsx` | 546 | **MIGRATE** | SF Symbols wrapper. Используется во всём приложении. Постепенно заменить на прямые `lucide-react` импорты. Файл удалить после полной миграции (PR-UI-17). | PR-UI-17 |
| `src/assets/iconsMap.ts` | — | **DELETE** | Используется только в `Icon.tsx`. Удалить вместе с ним. | PR-UI-17 |

### 3.4. Card components

| Файл | LOC | Действие | Причина | PR |
|---|---|---|---|---|
| `src/components/ui/macos/Card.tsx` | 394 | **MIGRATE** ⚠️ PARTIAL | Оставить как canonical. Алиас `MacOSCard` удалить. **Факт (25.08.2026):** canonical `Card` подтверждён (#2820), НО алиас `MacOSCard` жив в 329 JSX — миграция consumers перенесена в PR-UI-11 (см. статус PR-06). | PR-UI-06 → **PR-UI-11** |
| `src/components/ui/macos/MacOSStatCard.tsx` | 291 | **MIGRATE** ✅ #2820 → `StatCard` | Объединить с `MetricCard`. Стать canonical `StatCard`. Выполнено: файл переименован в `StatCard.tsx`, 40 JSX consumers мигрированы. | PR-UI-06 ✅ |
| `src/components/ui/macos/MacOSMetricCard.tsx` | 302 | **DELETE** ✅ #2820 | Дубликат `MacOSStatCard`. Мигрировать 33 потребителя на `StatCard`. | PR-UI-06 ✅ |
| `src/components/medical/MedicalCard.tsx` | 73 | **DELETE** | Используется только в `MediLabDemo.tsx`. Мёртвый код в реальном приложении. | PR-UI-17 |
| `src/components/medical/MetricCard.tsx` | 124 | **DELETE** | Используется только в `MediLabDemo.tsx`. Мёртвый. | PR-UI-17 |
| `src/components/medical/PatientCard.tsx` | 237 | **DELETE** | Используется только в `MediLabDemo.tsx`. Мёртвый. | PR-UI-17 |
| `src/components/medical/MedicalTable.tsx` | — | **DELETE** | Используется только в `MediLabDemo.tsx`. Мёртвый. | PR-UI-17 |
| `src/components/medical/index.ts` | — | **DELETE** | Barrel-file для мёртвого каталога. | PR-UI-17 |
| `src/components/layout/ModernCard.tsx` | 176 | **DELETE** ✅ #2820 | 0 импортов. Мёртвый. | PR-UI-06 ✅ |
| (новый) `src/components/ui/DataCard.tsx` | — | **CREATE** ⬜ | Новый canonical DataCard для очередей/appointments/lab results. ~150 LOC. **Факт (25.08.2026):** не создан в PR-UI-06; введение перенесено в PR-UI-11 (canonical card strategy, см. статус PR-06). | PR-UI-06 → **PR-UI-11** |

### 3.5. Table components

| Файл | LOC | Действие | Причина | PR |
|---|---|---|---|---|
| `src/components/ui/macos/Table.tsx` | 576 | **MIGRATE** → canonical `DataTable` | Базовый Table. Расширить: sticky header, sort, filter, pagination, selection, keyboard nav, density, skeleton, error state. ~700 LOC после миграции. | PR-UI-09 |
| `src/components/tables/EnhancedAppointmentsTable.tsx` | 2 279 (факт: 2 282) | **MIGRATE** ⬜ | God-компонент. После canonical DataTable — мигрировать все consumers на прямое использование DataTable с column-config. Файл сократить до ~400 LOC (только column definitions + actions). | PR-UI-09 |
| `src/components/common/Table.tsx` | 504 | **DELETE** | Дубликат `macos/Table.tsx`. Мигрировать 9 потребителей на canonical DataTable. | PR-UI-09 |
| `src/components/ResponsiveTable.tsx` | 468 | **DELETE** ⬜ | 0 импортов. Мёртвый. **Ownership-фикс (25.08.2026):** матрица ранее ошибочно относила к PR-17; canonical-владелец — PR-UI-09 (datatable migration territory, не dead-code cleanup). | PR-UI-17 → **PR-UI-09** |
| `src/components/cashier/RefundRequestsTable.tsx` | 430 | **MIGRATE** | Переписать на canonical DataTable. Сократить до ~150 LOC (columns + actions). | PR-UI-09 |
| `src/components/queue/QueueTable.tsx` | 239 | **MIGRATE** | Переписать на canonical DataTable. Сократить до ~100 LOC. | PR-UI-09 |

### 3.6. Form components

| Файл | LOC | Действие | Причина | PR |
|---|---|---|---|---|
| `src/components/ui/macos/Input.tsx` | 222 | **MIGRATE** → canonical `Input` | Оставить как canonical. | PR-UI-05 |
| `src/components/ui/macos/Select.tsx` | — | **MIGRATE** → canonical `Select` | Оставить. | PR-UI-05 |
| `src/components/ui/macos/Textarea.tsx` | — | **MIGRATE** → canonical `Textarea` | Оставить. | PR-UI-05 |
| `src/components/forms/ModernInput.tsx` | — | **DELETE** | 0 импортов. Мёртвый. | PR-UI-17 |
| `src/components/forms/ModernSelect.tsx` | — | **DELETE** | 0 импортов. Мёртвый. | PR-UI-17 |
| `src/components/forms/ModernTextarea.tsx` | — | **DELETE** | 0 импортов. Мёртвый. | PR-UI-17 |
| `src/components/forms/ModernForm.tsx` | — | **DELETE** | 0 импортов. Мёртвый. | PR-UI-17 |
| `src/components/forms/ResponsiveForm.tsx` | — | **DELETE** | 0 импортов. Мёртвый. | PR-UI-17 |
| `src/components/forms/index.ts` | — | **DELETE** | Barrel-file для мёртвого каталога. | PR-UI-17 |

### 3.7. Dialog/Modal components

| Файл | LOC | Действие | Причина | PR |
|---|---|---|---|---|
| `src/components/ui/macos/Modal.tsx` | 511 | **MIGRATE** → canonical `Modal` | Оставить. Focus trap + escape + overlay уже есть. | — |
| `src/components/ui/macos/Dialog.tsx` | — | **KEEP** | Оставить. | — |
| `src/components/dialogs/ModernDialog.tsx` | 209 | **MIGRATE** | 6 импортов. После аудита — либо мигрировать на Modal, либо оставить как тонкую обёртку. Решить в PR-UI-06. | PR-UI-06 |
| `src/components/common/Modal.tsx` | — | **DELETE** | Дубликат macos/Modal. 0 прямых импортов вне common/index.ts. | PR-UI-17 |

### 3.8. Empty/loading/error state

| Файл | LOC | Действие | Причина | PR |
|---|---|---|---|---|
| `src/components/ui/macos/AppState.tsx` | 240 | **MIGRATE** ✅ #2835 (07a-8a) → canonical `AppState` | Оставить `AppLoading`, `AppEmpty`, `AppError`. Удалить импорт `MacOSEmptyState` (строка 3). Выполнено: рендеринг internalized (inline md+minimal), зависимость от MacOSEmptyState устранена. | PR-UI-07 ✅ |
| `src/components/ui/macos/MacOSEmptyState.tsx` | 191 | **DELETE** ✅ #2836 (07a-8b) | Дубликат `AppEmpty`. 33 потребителя мигрировать на `AppEmpty`. Выполнено полностью: файл + barrel-export + legacy-тест удалены (−335 LOC); runtime-упоминаний 0. | PR-UI-07 ✅ |
| `src/components/ui/macos/Skeleton.tsx` | 188 | **KEEP** | Canonical skeleton. 34 потребителя. Оставить. | — |
| `src/components/ui/macos/Alert.tsx` | — | **KEEP** | Canonical alert. Оставить. | — |

### 3.9. Button components

| Файл | LOC | Действие | Причина | PR |
|---|---|---|---|---|
| `src/components/ui/macos/Button.tsx` | 257 | **MIGRATE** ✅ #2819 + P1a | Canonical. Сократить variants с 11 до 6 (default → `secondary`, primary, ghost, outline, danger, link). Удалить `success`, `warning`, `destructive`, `error` (дубликаты). Тип `variant` → literal-union (tsc-error на unknown). Дополнено P1a (25.08.2026): ещё 32 non-canonical варианта мигрированы. | PR-UI-05 ✅ |
| `src/components/admin/IconButton.tsx` | — | **MIGRATE** | Оставить как специализированный admin-компонент, но наследовать от canonical Button. | — |

### 3.10. CSS files (cleanup)

| Файл | LOC | Действие | Причина | PR |
|---|---|---|---|---|
| `src/styles/cursor-effects.css` | 520 | **DELETE** ⬜ | Мёртвый CSS. Содержит ripple/lift/transform эффекты, которые user явно запретил. **Ownership-фикс (25.08.2026):** владелец удаления — PR-UI-17 (решение Codex review #2810: 9 interaction-классов ещё потребляются MediLabDemo; PR-08 не должен совмещать glass/animation canonicalization с legacy-decommission). **PR-08 verification (#2838, 25.08.2026, main `ae7236cb6`):** runtime-dead подтверждён — **0 runtime CSS imports anywhere in `src/`** (AC3a ✓; ранее матрица заявляла «Импортёр на срез — только `MediLabDemo.tsx`» — **коррекция**: проверка на `ae7236cb6` показала 0 импортов в `MediLabDemo.tsx` и нигде в `src/`). **4 stale audit-manifest entries** в `frontend/src/utils/frontendAudit.tsx` (lines 309, 330, 762, 765 — object keys + array elements, NOT runtime imports; AC3b, PR-17 owned cleanup). Файл 520 LOC жив как физический артефакт, runtime-dead. | PR-UI-17 (intact) |
| `src/styles/sidebar-buttons.css` | 75 | **DELETE** ✅ #2810 | Мёртвый CSS. Импортировался только в `UnifiedSidebar.tsx`. Содержал `transform: translateY(-3px) !important`. **Факт:** удалён в PR-UI-03 (раньше плана — матрица относила к PR-08). | PR-UI-08 → **PR-UI-03** (факт) |
| `src/styles/accessibility.css` | 266 | **KEEP** | Сильная сторона проекта. WCAG 2.1 AA compliance. | — |
| `src/styles/animations.css` | 380 (факт на `ae7236cb6`: 76) | **MIGRATE** ✅ #2838 | Удалить keyframes с transform/translateY. Оставить fade-in/slide-down (без transform). Применить `@media (prefers-reduced-motion: reduce)` ко всем. **PR-08 (#2838, 25.08.2026):** выполнено — 380 → 76 LOC (~150 LOC удалено, ~150 LOC 0-consumer утилит+keyframes). Deleted: animate-wave/shimmer/gradient + 3 keyframes, card-enter/-active/-exit + 2 keyframes, modal-enter/-active, notification-enter/-active, button-press, icon-bounce, text-reveal, list-item-enter/-active, table-row-enter/-active, mac-animate-fade-in/slide-in + macFadeIn/macSlideIn, loading-skeleton, hover-rotate, transition-smooth, progress-animate + progress keyframe. KEPT: animate-spin (38 loaders), animate-pulse (4 opacity-only skeletons), hover-lift/hover-scale (demo-perimeter, PR-17 owned). D4: legacy `fadeInUp/Left/Right/Scale` + `.animate-fade-in-*` + `.animate-delay-*` удалены после equivalence-migration в `tokens.css` canonical `mac-entrance-*`/`mac-delay-*` primitives. | PR-UI-08 ✅ |
| `src/styles/admin-styles.css` | 379 | **MIGRATE** | Аудит. Удалить дубликаты с tokens.css. | PR-UI-02 |
| `src/styles/responsive.css` | 476 | **KEEP** | Полезные responsive utilities. | — |
| `src/styles/header-new.css` | 202 | **KEEP** | Стили для HeaderNew. После PR-UI-04 — обновить. | — |
| `src/styles/full-width.css` | 32 | **KEEP** | Полезная утилита. | — |
| `src/styles/emr-tokens.css` | 327 | **KEEP** | EMR-специфичные токены. Оставить. | — |
| `src/styles/unified-sidebar.css` | 302 | **DELETE** ✅ #2810 | Стили для удалённого UnifiedSidebar. **Факт:** удалён в PR-UI-03 (раньше плана — матрица относила к PR-17). | PR-UI-17 → **PR-UI-03** (факт) |

### 3.11. Brand & landing

| Файл | LOC | Действие | Причина | PR |
|---|---|---|---|---|
| `src/config/brand.ts` | 62 | **MIGRATE** ⬜ | Унифицировать `name` и `shortName` на "Clinic OS". Удалить "MediClinic Pro". Указать реальные пути к logo. **Факт (срез 25.08.2026):** `name` всё ещё 'MediClinic Pro'; `public/brand/` не существует. | PR-UI-10 |
| `public/brand/logo.svg` | — | **CREATE** | Новый SVG-логотип. Медицинский teal + белый. Минималистичный. | PR-UI-10 |
| `public/brand/logo-mark.svg` | — | **CREATE** | Монограмма 32×32 для favicon. | PR-UI-10 |
| `public/favicon.ico` | — | **REPLACE** | Заменить текущий (по умолчанию Vite) на logo-mark. | PR-UI-10 |
| `src/pages/landingContent.ts` | — | **MIGRATE** ⬜ | Удалить "MediClinic Pro" → "Clinic OS". **Факт (срез 25.08.2026):** осталось 20 упоминаний в src (план исходил из 36). | PR-UI-10 |
| `src/pages/Landing.tsx` | 806 | **MIGRATE** | Полный редизайн. Hero с реальным screenshot. Workflow diagram. Убрать FEATURE_VISUALS icon-grids. | PR-UI-16 |

---

## 4. Sprint Plan — 19 PR за 6 спринтов (18 исходных + PR-UI-19 C-6 gap-closure, введён v1.8)

![Sprint Plan](./assets/sprint_plan.png)

| Sprint | Недели | PR | Тема | Story Points | Статус (срез 25.08.2026) |
|---|---|---|---|---|---|
| **1. Foundation** | 1-2 | PR-UI-01, 02, 03 | Единый ThemeProvider + token source + language fix | 9 SP | ✅ DONE (02 — with legacy follow-up → PR-17) |
| **2. App Shell** | 3-4 | PR-UI-04, 05, 06 | Единый AppShell + Button + Card primitives | 16 SP | 04 ✅ · 05 ✅ · 06 ⚠️ PARTIAL (хвост → PR-11) |
| **3. State patterns** | 5-6 | PR-UI-07, 08, 09 | Loading/Empty/Error + убрать glass + DataTable | 17 SP | 07 ✅ (+серия 07a) · 08 ✅ (#2838) · 09 🟡 (SP не кредитованы до 09e-2; 09a ✅ #2843 → §4.1.6; 09b ✅ #2848 → §4.1.7; 09c ✅ COMPLETE — #2857/#2860/#2861/#2862 → §4.1.8; 09d ✅ #2870 → §4.1.9; 09e-1 ✅ #2872 → §4.1.9; 09e-2 LOC-редукция — DEFERRED §4.1.9) |
| **4. Branding** | 7-8 | PR-UI-10, 11, 12 | Branding + Dashboard + EMR/Queue/Table UX | 16 SP | 🟡 IN FLIGHT (10 ✅ #2867 + `66c7ceff`; 11 🟡 — 12 инкрементов 11-1..11-12 merged (#2871/#2873/#2876/#2878/#2880/#2882/#2884/#2886/#2888/#2889/#2892/#2894), остаток MacOSCard-потребителей — 12 файлов fresh grep 29.08 @ `64f73d40`; 12 ✅ COMPLETE — 12-1 #2885, 12-2 #2890, 12-3 #2891, 12-4 #2893 → §4.1.10) |
| **5. Migration** | 9-10 | PR-UI-13, 14, 15, 19 | RegistrarPanel + Doctor + Cashier + Navigation i18n (C-6) | 27 SP | 19 ✅ (#2879 → `faace538`); 13/14/15 ⬜ — все три = god-panel decomposition (архитектурное решение пользователя, см. §4.1.10) |
| **6. Polish** | 11-12 | PR-UI-16, 17, 18 | Landing + cleanup (incl. M-8) + visual regression | 18 SP | ⬜ не начаты |

**Итого:** 19 PR · 103 story points · ~12 недель (3 месяца) при 1 разработчике (18 исходных PR · 98 SP + PR-UI-19 «Navigation i18n (C-6)» · 3 SP + 2 SP к PR-UI-17 за M-8 ownership — оба введены v1.8 из audit-completeness reconciliation, Приложение C).

**Прогресс на 29.08.2026 (main `64f73d40`, срез v1.9):** полностью выполнено 11 из 19 PR — 48/103 SP (PR-UI-01–05, 07, 08, 10, 12, 19; PR-UI-06 — ⚠️ PARTIAL, хвост закрывается в PR-UI-11; PR-UI-09 — 🟡 structural COMPLETE, AC2 DEFERRED → 09e-2: 8 SP НЕ кредитуются до доставки per AGENTS_UI §13 «DEFERRED ≠ completed coverage»; PR-UI-11 — 🟡 IN PROGRESS, 12 инкрементов merged, MacOSCard-остаток 12 файлов). Поддерживающие коммиты: Phase 0 ratchet, C-1, C-4 (macos.css prefers-color-scheme cleanup), C-5, P1a (Button variants). Серия PR-UI-07a (12 sub-PR, #2824–#2836) завершена физическим decommission MacOSEmptyState (#2836). PR-UI-08 (#2838, 25.08.2026) — glass/animation canonicalization, D1–D8 rulings, см. §7 PR-UI-08 + §4.1.2 ledger. **Phase 2C info-family definition-only remediation (commit `e16f3b0c`, 26.08.2026): VERIFIED — CI 30/30 terminal, 22 success + 8 expected skipped + 0 failures; ratchet 155/301 PASS; см. §4.1.3 ledger.** **Phase 2A `--mac-text-muted` consumer migration (commit `9b1ef5d`, 26.08.2026): VERIFIED — CI 33/33 terminal, 25 success + 8 expected skipped + 0 failures (Regression Audit Gate ✅, Frontend e2e ✅); ratchet 154/280 PASS; см. §4.1.4 ledger.** **Phase 2B-A `--mac-spacing-md` single-usage remediation (PR #2844, merge `26410a025`, 26.08.2026): VERIFIED — CI merge commit 32/32 terminal, 25 success + 7 skipped + 0 failures; ratchet 154/279 PASS; см. §4.1.5 ledger.** **PR-UI-09a DataTable foundation remediation (PR #2843, squash merge `8143a361`, 26.08.2026): MERGED-VERIFIED — CI 34/34 terminal, 26 success + 8 skipped + 0 failures; ratchet 154/281 PASS; см. §4.1.6 ledger.** **PR-UI-09b decommission dead Table implementations (PR #2848, squash merge `11b423990`, 27.08.2026): MERGED-VERIFIED — CI merge commit 35/35 terminal, 26 success + 9 skipped + 0 failures; ratchet 154/281/11917 PASS; см. §4.1.7 ledger.** **PR-UI-09c live-consumer migration (4 инкремента: 09c-1 PR #2857 → squash `c8464c81`; 09c-2 PR #2860 → squash `e35df1f0`; 09c-3 PR #2861 → squash `e17d261b`; 09c-4 PR #2862 → squash `028ab397`; 28.08.2026): MERGED-VERIFIED — CI terminal на всех 4 merge-коммитах, 0 failures; ratchet 154/281/11855 PASS; см. §4.1.8 ledger.** **PR-UI-09d final alias-cleanup (PR #2870, squash merge `7243a108`, 28.08.2026): MERGED-VERIFIED — CI terminal 0 failures; ratchet 154/281/11855 PASS (вклад 0); см. §4.1.9 ledger.** **PR-UI-09e-1 DataTable row virtualization — PR-UI-09 AC4 (PR #2872, squash merge `d20cde25`, 28.08.2026): MERGED-VERIFIED — CI terminal 0 failures; zero-delta для живых поверхностей (A/B DOM ×4); см. §4.1.9 ledger.** **PR-UI-10 branding (PR #2867, squash merge `865ab5d8`, 28.08.2026, + follow-up #2869 → `66c7ceff`): MERGED-VERIFIED — 13 файлов +171/−51; public/brand/{logo,logo-mark}.svg созданы; brand name/shortName = 'Clinic OS'; 0 «MediClinic Pro» в src (fresh grep 29.08).** **PR-UI-11-1 AdminDashboard data-first + canonical DataCard (PR #2871, squash merge `1378d6ef`, 28.08.2026): MERGED-VERIFIED — 10 файлов +1359/−151 (AdminDashboard +673, DataCard.tsx +249, DataCard.test.tsx +163).** **PR-UI-11-2 миграция 6 admin MacOSCard consumers → canonical Card (PR #2873, squash merge `32edbc20`, 28.08.2026): MERGED-VERIFIED — 6 файлов +18/−18.** **PR-UI-11-3..11-12 MacOSCard-миграция (10 инкрементов, 28–29.08.2026: 11-3 #2876 → `b5dc46d7`; 11-4 #2878 → `0eb96756`; 11-5 #2880 → `7a511d7d`; 11-6 #2882 → `15e484bc`; 11-7 #2884 → `68f51d9d`; 11-8 #2886 → `aef6b344`; 11-9 #2888 → `d5bcf003`; 11-10 #2889 → `1dac9278`; 11-11 #2892 → `0c9b621c` (cardiology); 11-12 #2894 → `61468afe` (dermatology)): MERGED-VERIFIED — MacOSCard-потребители 61 → 12 файлов (fresh grep 29.08 @ `64f73d40`).** **PR-UI-19 Navigation i18n (PR #2879, squash merge `faace538`, 29.08.2026): MERGED-VERIFIED — 0 кириллических nav-label в routeRegistry; nav.* ×51 ключ ×5 локалей; см. §4.1.10.** **PR-UI-12 EMR+Queue+Table UX (4 инкремента: 12-1 #2885 → `4199b9c2`; 12-2 #2890 → `f4d577d7`; 12-3 #2891 → `26347af3`; 12-4 #2893 → `64f73d40`; 29.08.2026): MERGED-VERIFIED — все 4 AC-пункта плана закрыты (см. статус §7 и §4.1.10).** Остаток: 55 SP (в т.ч. 8 SP PR-UI-09/09e-2 — до доставки deferral не кредитуется; +2 SP к PR-UI-17 за M-8 ownership, v1.8); PR-UI-09 — 🟡 structural COMPLETE (09a–09e-1; AC2 DEFERRED §4.1.9 — 6-полей запись; SP не кредитованы); PR-UI-11 — 🟡 IN PROGRESS (11-1..11-12 merged; остаток: MacOSCard жив в 12 файлах, fresh grep 29.08 @ `64f73d40`). Ratchet на срез v1.7 (`4228c32d`): 154/281/11855, gate PASS (noFallback −118 к срезу 27.08 (11973): −56 — мёртвые таблицы PR #2848 (см. §4.1.7), −28 — QueueTable inline-стили → CSS-классы (09c-2, #2860), −34 — EnhancedAppointmentsTable inline td/th → token CSS (09c-4, #2862); names/usages — без изменений; +4 drift PR #2847 (2FA recovery-phone, вне UI-audit workstream) сохранён в атрибуции §4.1.6; drift #2863/#2864 (auth, вне UI-audit workstream) ratchet не меняет). Ratchet на срез v1.8 (`ad2f44ac`): **156/282/11883, gate PASS** (к 11855: +2 names / +1 usages / +28 noFallback — прирост полностью атрибутирован PR-UI-11-1 #2871: замер на `1378d6ef` = уже 156/282/11883 до merge 09e-1; PR-UI-11-2 #2873 и 09d/09e-1 вклад 0 — zero-delta / `__tests__` вне сканера; #2874 backend-jobs ratchet не меняет). Ratchet на срез v1.9 (`64f73d40`): **156/282/11883, gate PASS — без изменений к v1.8** (вклад всех срез-инкрементов = 0: PR-UI-11-3..11-12 — MacOSCard→Card swap-миграции без новых style-literals; PR-UI-19 — labelKey в данных + t()-резолюция в Sidebar; PR-UI-12-1..12-4 — ratchet-neutral by construction: tokens.css-классы с fallback / флаги-пропсы / skeletons / sticky-viewport через существующий scrollViewportStyle-механизм; см. §4.1.10). Установленная дисциплина исполнения: inventory → decision gate → baseline → implementation → proof → Tier-1 → E2E → PR → STOP → explicit merge approval → post-merge verification.

### 4.1.1 Handoff от параллельного QA/UI-audit трека (25.08.2026, верифицировано на main `434cf34`)

> Источник: consolidated codex-findings audit (39 замечаний, PR #2806–2827) + ре-верификация grep/import-сканом на `434cf34`. Не входит в PR-UI-нумерацию; зафиксировано, чтобы находки не потерялись при смене трека. Дальнейшую работу по этому плану ведёт соседний агент; QA/UI-audit трек переходит exclusively на `UI_AUDIT_PLAN.md` (корень репо).

**Закрыто параллельным треком (перепроверено на `434cf34`, действий не требуется):**

- **P1a Button variants** — 32/32 non-canonical usages мигрированы (`aebe29d`); ре-скан на `434cf34` (import-verified, только файлы с `Button` из `ui/macos`): **0 non-canonical**. Сырые rg-попадания `variant="success|warning|outlined|contained"` по src/ (≈63) — это Badge/Card/Alert/custom-компоненты, canonical для них.
- **P0 Playwright gate policy** — Tier-1 48/47 blocking в CI (`EXPECTED_COUNT=47`, retries=0) + two-tier deferral protocol в AGENTS_UI §13.
- **MacOSEmptyState decommission** — подтверждён: 0 runtime-упоминаний (6 остаточных вхождений — комментарии и имя legacy-теста).

**Открыто — кандидаты на включение в этот план:**

1. **P1b AppEmpty framing (product decision, не трекается планом):** AppEmpty internalized `variant="minimal"` verbatim (#2835) — transparent/без рамки vs прежний default framed card (bg + border + radius). Runtime-доказано в codex-audit: 26+ мигрированных empty states потеряли framed look; осознанно исполнителем (`PR_UI_07a_1b_PRE_PR_REPORT.md:190`), но продукт решение не подтверждал. Варианты: принять minimal как canonical ИЛИ добавить `framed` prop.
2. **`ButtonVariant | string` escape (Button.tsx:8) — enforcement-ready:** на HEAD 0 non-canonical usages → escape можно убрать, получив compiler-защиту; canonical-тип уже зафиксирован этим планом (см. §PR-UI-05: `type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'outline' | 'danger' | 'link'`). Микро-PR при ближайшем касании Button.
3. **P2-гигиена:** (a) API contract всё ещё рекламирует vibrant/glass/gradient (5 refs в `src/types/generated/api.ts` + backend `user_management.py:44-46`) при frontend silent→`auto` — нужен backend-фикс + regen; (b) exec-bit `100755` на 870 src/-файлах; (c) `ComponentType<any>` — RoleGuard.tsx:78, RequireAuth.tsx:157, PWAInstallPrompt.tsx:110; (d) DESIGN_SYSTEM.md:207 запрещает `design-system/tokens.css`, а :35 числит его canonical-источником — противоречие в одном доке.
4. **Координация с Tier-1 expansion:** QA-трек готовит expansion invariant 47→67 (+20 authenticated-маршрутов: role ×6, specialty ×2, action ×5, rbac-deny ×4, admin family ×3 — users/webhooks/telegram). После приземления UI-PRы на этих поверхностях получают blocking e2e-защиту; rbac-deny уже на crash-capture parity (PR-QA-04, `434cf34`).

### 4.1.2 PR-UI-08 Completion Ledger (#2838, 25.08.2026)

> Источник: post-merge verification PR #2838 (squash `ae7236cb6`, parent `c9ea39edd`, merged by explicit user approval 25.08.2026). Зафиксировано, чтобы SSOT оставался актуальным после PR-08 (rule #7 AGENTS_UI). Не входит в PR-UI-нумерацию; ownership follow-ups перенаправлены в их назначенные PR.

**Закрыто PR-08 (D1–D8 rulings, all applied):**
- **Glass/animation canonicalization:** 23 файла, +85/−720. Backdrop migration (AC1: 27→7 ≤10 ✓); hover/transform unification (AC2: 7→0+D3 exception ✓); animations.css cleanup (380→76 LOC, ~150 LOC 0-consumer утилит+keyframes удалено); D4 migration (15/15 MediLabDemo refs migrated to canonical `mac-entrance-*`/`mac-delay-*` primitives in `tokens.css` +54 LOC; equivalence-by-construction, byte-identical legacy values).
- **D7 orphan:** `components/AnimatedTransition.tsx` (314 LOC, NOT `MacOSEmptyState`) физически удалён. 4-proof: (1) 0 importers via grep, (2) 0 dynamic/string imports sweep, (3) tsc --noEmit exit 0 post-deletion, (4) canonical `ui/macos/AnimatedTransition` covers production consumers (DoctorPanel:15, QueueView:22, WelcomeView:58 via barrel).
- **D8 InteractivePanel:** hover transform удалён, calm shadow+border feedback only.
- **D6 documented CSS exceptions:** `.mac-modal-backdrop` (`tokens.css:495`) + `.clinic-ops-nav-bar` (`macos.css:386`) backdrop KEPT (sticky-overlay semantics).
- **D3 documented exception:** `mac-modal-slide-up` keyframe (Modal.tsx inline) KEPT — Modal entrance animation.

**Ratchet:** PASS — 8 improvements, 0 regressions (см. §7 PR-UI-08 banner для детального списка).

**Tier-1 + CI:** local tsc/vitest/build/lint/check-theme/icon-controls + авторитативный CI на merged SHA `ae7236cb6` (33 runs = 25 success / 8 skipped / 0 failures).

**Follow-ups (не part of PR-08, ownership intact):**
1. `cursor-effects.css` decommission — **PR-UI-17 owned** (Codex review #2810 ruling intact). PR-08 verified runtime-dead (520 LOC, 0 runtime imports — AC3a ✓; 4 stale audit-manifest refs in `frontendAudit.tsx` — AC3b, PR-17 cleanup).
2. `colorScheme.ts` ROOT_STYLE_PROPERTIES vestigial refs (PR-02 glass-scheme removal residual) — **PR-17 owned** candidate.
3. `HeaderNew.tsx` vestigial glass refs — minor follow-up, не blocking.
4. Additional CSS backdrop surfaces (AIChatWindow/ModernDialog/EMRContainerV2/ModernToast/ModernFilters/DoctorTemplatesPanel/AppointmentWizardV2/MacOSDemo) — **separate cleanup track**, не blocking.
5. UI-audit track C-4 (`c9ea39edd`, 25.08.2026) — separate commit BEFORE PR-08 (parent of `ae7236cb6`); removed `.glass` rule + legacy `prefers-color-scheme` vars from `macos.css`. Attributed to C-4 UI-audit track, NOT to PR-08.
6. BS-44 local environmental false-positive — pre-existing (verified on clean main, CI green).
7. lifecycle-label drift (`decision:possible-duplicate` bot false-positive as in #2836) — not blocking.

**Verification artifacts:** `/home/z/my-project/scripts/merge_pr_2838.sh` (squash-merge script), `/home/z/my-project/worklog.md` Task 34 (post-merge verification entry, 10/10 verification points PASS).

### 4.1.3 Phase 2C — Info-Family Definition-Only Remediation (commit `e16f3b0c`, 26.08.2026)

> Источник: C-3 Phase 2C info-family remediation (commit `e16f3b0c656ba05d1e0de0a6bfd7cae256483aef`, direct push to main as fast-forward from `a1d47f17`, 26.08.2026). **Status: VERIFIED (not merely MERGED)** — post-push SHA + full CI terminal + ratchet PASS. Definition-only scope: tokens.css only, +3/-0, no consumer migration, no admin.css, no dark-mode, no baseline/snapshot updates.

**Закрыто Phase 2C (3 canonical info-family token definitions added to `src/design-system/tokens.css`):**

```
--mac-info: #5ac8fa;
--mac-info-bg: color-mix(in srgb, var(--mac-info), transparent 86%);
--mac-info-border: var(--mac-info);  /* SOLID */
```

- **Value provenance — `--mac-info = #5ac8fa`**: единственный cyan reference в кодовой базе — `AnimatedLoader.tsx:10` fallback `info: 'var(--mac-info, #5ac8fa)'`.
- **Value provenance — `--mac-info-bg`**: family pattern (success/warning/error all use `color-mix(... transparent 86%)`); C-3-B.3 mapping to `--mac-accent-bg`; admin.css live fallback `rgba(0,122,255,0.12) ≈ 12% alpha` — все 3 источника согласованы → 14% alpha cyan.
- **Value provenance — `--mac-info-border = var(--mac-info)` SOLID**: C-3-B.3 audit — 3/8 original consumers имели explicit SOLID `--mac-accent-blue` fallback; 0/8 имели `--mac-accent-border` fallback; commit rationale прямо цитирует SOLID fallbacks.

**Diff scope (exact):** `1 file changed, 3 insertions(+)`. Файл: `frontend/src/design-system/tokens.css`. 0 deletions, 0 inline-комментариев (initial inline comment on `--mac-info-border` removed surgically pre-commit per user instruction — historical intent уже в worklog).

**Metrics (ratchet --check, baseline `f837bc966` → current `e16f3b0c`):**
- `undefinedVarNameCount`: 163 → **155** (-8 total, -3 от этого edit)
- `undefinedVarUsages`:    330 → **301** (-29 total, -18 от этого edit)
- Все остальные 9 improvements (varUsagesNoFallback -70, cssHexOutsideTokens -8, tsxHex -2, duplicateKeyframesNameCount -2, unreferencedFileCount -1, prefersSchemeRootBlocks -1, и др.) — от upstream commits между baseline и HEAD, не от этого edit.
- Ratchet PASS: 0 регрессий. drift = 0.

**Beneficial side-effect (not in-scope, accepted as-is):**
- `ServiceCatalog.tsx:202` stomatology category color был ранее broken (`var(--mac-info)` был undefined → background-color invalid → transparent). После этого commit он resolves в `#5ac8fa` cyan — визуально distinct от physiotherapy's `#007aff` blue. Strict improvement, не regression. C-3-B.3 ранее откладывал это как UX decision; теперь resolved favorably.

**CI verification (commit `e16f3b0c` на `origin/main`):**
- Total check-runs: 30 (30 terminal).
- 22 success: Frontend unit/e2e/build/lint, Backend тесты, Gate D (PostgreSQL + concurrency), Frontend-Backend Parity, Интеграционные тесты, role-system-check, CI Scope, Context Boundary Integrity, Metadata checks, Scan for leaked secrets, Security сканирование (x2), Supabase Preview, Production readiness report, Docker сборка, Генерация документации, Качество кода, **Regression Audit Gate**, Vercel deployment.
- 8 skipped (expected для direct-main push, не PR/release): Load Tests (k6), Staging readiness report, PR Required Gate, Notify-on-failure (x2), Telegram Mini App Release Gate, DAST ZAP (Nightly), Build + upload source maps to Sentry.
- 0 failures. Combined state: success.
- Особое внимание (per user emphasis): Regression Audit Gate ✅, Frontend e2e ✅.

**Process note — fast-forward sync pre-commit:**
- Local HEAD был 2 commits позади origin/main (`f26902f8` vs `a1d47f17`); upstream 2 commits — оба docs-only (`docs/AGENTS_UI.md +74`, `docs/UI_REMEDIATION_PLAN.md +82`), `tokens.css` UNCHANGED между ними.
- User-approved Option A: `git stash` (3-line edit) → `git merge --ff-only origin/main` (clean FF, NO rebase, NO merge commit) → `git stash pop` (clean apply, 0 conflicts) → re-verify diff = +3/-0 → commit → push.
- Post-push: `local HEAD == origin/main == e16f3b0c`, behind=0, ahead=0.

**Follow-ups (DEFERRED, требуют отдельного user approval):**

1. **`--info-color` legacy alias** (`tokens.css:26 = --info-color: var(--mac-accent);`): сейчас aliases info → accent (blue `#007aff`), что теперь КОНТРАДИКТ-прежнему новому `--mac-info` (cyan `#5ac8fa`). Migration deferred.
2. **Dark-mode values**: `.dark-theme` selector в tokens.css НЕ определяет `--mac-info` / `--mac-info-bg` / `--mac-info-border`. Light-mode definitions наследуются в dark mode (`#5ac8fa` cyan рендерится well on dark). Acceptable, не theme-optimized. Deferred.
3. **Admin utility class names**: 4 generated utility classes в admin.css имеют `var-mac-info-bg` / `var-mac-info-border` в ИМЕНАХ классов (CSS bodies уже мигрированы в C-3-B.3). Class-name cleanup — отдельная задача. Deferred.
4. **Dead-code consumers** (6 usages в `AIAnalytics.css` / `WaitTimeAnalytics.css`): direct `var(--mac-info-bg)` / `var(--mac-info-border)` references. Сейчас resolve correctly (cyan 14% bg + solid cyan border), но components остаются unrendered dead code. Dead-code cleanup — отдельная задача. Deferred.
5. **`--mac-text-muted`** (21 usage): per-usage semantic audit — НЕ remediation. Token используется в разных ролях (caption, hint, separator/icon, button label, disabled/future state). Нельзя заменить одним global `--mac-text-secondary`. Требуется таблица: Usage | File:line | Semantic role | Current property | Secondary? | Tertiary? | Evidence | Confidence. Отдельный read-only decision gate. **[RESOLVED 26.08.2026 → §4.1.4: audit выполнен (21/21 → tertiary), remediation VERIFIED на `9b1ef5d`.]**
6. **`--mac-spacing-md`** (cardiology.css): per-usage semantic inspection. Отдельный LOW-risk PR (2 изменения). Deferred. **[PARTIALLY RESOLVED 26.08.2026 → §4.1.5: фактически 7 usage на момент аудита (не 2); Phase 2B-A (PR #2844, merge `26410a025`) закрыл 1 из 7 — cardiology.css:64 → `--mac-spacing-4` (runtime 16px); остаток — 6 usage (cardiology.css:70, 162, 225, 235, 236, 299), deferred.]**
7. **Plan-SSOT/governance update** (этот раздел) выполнен; further governance updates — отдельные stage transitions per user approval.

**Verification artifacts:** `/home/z/my-project/worklog.md` Task IDs `2C-bg-border`, `2C-B`, `2C-post-cleanup`, `2C-commit-push-ci` (audit trail).

**STOP-AFTER-VERIFIED:** Phase 2C закрыта как VERIFIED. Следующий технический read-only этап (`--mac-text-muted` per-usage semantic audit) НЕ запускается автоматически — требует отдельной команды пользователя.

### 4.1.4 Phase 2A — `--mac-text-muted` Consumer Migration (commit `9b1ef5d`, 26.08.2026)

> Источник: Phase 2A undefined-token consumer remediation (commit `9b1ef5d47c77891fcc3c258e951f362b040fece0`, direct push to main as fast-forward from `69bdc9a9`, 26.08.2026). **Status: VERIFIED (not merely MERGED)** — post-push SHA + full CI terminal (33/33, 0 failures). Scope: ровно 21 consumer replacement в 5 файлах, строго +21/−21; НОВЫХ tokens НЕ создано; значения `--mac-text-secondary` / `--mac-text-tertiary` НЕ изменены; `.ltw-text-muted` НЕ удалён; hover НЕ добавлен; baseline/snapshots НЕ обновлены.

**Закрыто Phase 2A (21 usage `var(--mac-text-muted)` → `var(--mac-text-tertiary)`):**

- `--mac-text-muted` НЕ БЫЛ определён ни в canonical tokens.css, ни в legacy macos-tokens.css (git-history: 0 коммитов с определением). Все 21 usage молча наследовали цвет родителя (обычно `--mac-text-primary`) — задуманная muted-де-эмфаза терялась в runtime (silent UI bug; доказан computed-style fixture: light → rgb(0,0,0), dark → rgb(255,255,255)).
- Per-usage semantic audit (read-only, base `69bdc9a9`): 21/21 → существующий canonical tertiary tier (#5d6f84 light / #636366 dark); 20/21 HIGH confidence, 1/21 MEDIUM (lab.css:662 disabled/future state). Semantic split не потребовался: все роли (caption, hint, separator/icon, button label, disabled) разделяют один visual intent де-эмфазы; tertiary = canonical muted tier. Закрывает §4.1.3 follow-up #5.

**Diff scope (exact):** 5 файлов, +21/−21, единственное изменение на строку — `var(--mac-text-muted)` → `var(--mac-text-tertiary)` (программно верифицировано: каждая строка diff отличается только именем токена):

- `frontend/src/pages/lab.css` ×6 (314, 342, 384, 396, 528, 662)
- `frontend/src/pages/patient.css` ×6 (303, 420, 542, 563, 573, 623)
- `frontend/src/components/admin/AdminSecurityDashboard.tsx` ×5 (153, 224, 247, 294, 325)
- `frontend/src/components/laboratory/LabTemplateWorkbench.css` ×3 (220, 324, 519)
- `frontend/src/components/patient/WebAuthnRegistration.tsx` ×1 (138)

Residual `var(--mac-text-muted)` в `frontend/src/`: 0.

**Metrics (ratchet --check, delta этого PR изолирована против base `69bdc9a9`):**
- `undefinedVarNameCount`: 155 → **154** (−1; `--mac-text-muted` покинул undefined-список)
- `undefinedVarUsages`: 301 → **280** (−21)
- `varUsagesNoFallback`: 11933 → 11933 (0; оба варианта без fallback)
- Historical baseline (f837bc966 → now): names 163→154 (−9: −8 прошлые фазы, −1 этот PR), usages 330→280 (−50: −29 прошлые фазы, −21 этот PR)
- Предсказание аудита (154/280) совпало бит-в-бит. Drift = 0. PASS.

**Gates (pre-commit):** tsc 0 errors; Vitest 165 файлов / 1224/1224; vite build exit 0; runtime computed-style fixture 84/84 (light+dark: pre-fix inheritance-баг доказан, post-fix canonical resolution #5d6f84/#636366 доказана); Tier-1 Playwright chromium 48/48 (6 спеков, visual snapshots чисты); production bundle: 0 вхождений `mac-text-muted`, все 3 определения tertiary в главном CSS-бандле.

**Reachability (нахождение этапа):** 14/21 LIVE (lab.css ×6, patient.css ×6, LabTemplateWorkbench.css ×2 — каждый класс имеет TSX-потребителя, компоненты в ROUTE_COMPONENTS/бандле); 7/21 DEAD (AdminSecurityDashboard.tsx — 0 importers, вне бандла; WebAuthnRegistration.tsx — 0 importers, в бандле только i18n-строки; `.ltw-text-muted` — 0 потребителей). Визуально изменятся 14 элементов (light: 18.84:1 inherited → 4.63:1 tertiary; dark: 17.01:1 → 2.84:1) — восстановление задуманной muted-иерархии. Ratchet-дельта не зависит от reachability (сканер читает исходники).

**Known follow-up (зафиксирован пользователем как отдельные решения, НЕ часть этого PR):**

1. **Dark-mode `--mac-text-tertiary` contrast = 2.84:1** на `--mac-bg-primary-dark` (#636366 на #1c1c1e), 2.33:1 на bg-secondary-dark — ниже WCAG AA 4.5:1. Этот PR приводит 21 consumer к существующему canonical tier (консистентность с каноном; все существующие tertiary-consumers рендерятся так же), но НЕ изменяет значение самого токена. Dark tertiary contrast improvement — **отдельный будущий design-system decision** (референс: dark-secondary #8e8e93 = 5.22:1).
2. **Dead-code cleanup**: AdminSecurityDashboard.tsx, WebAuthnRegistration.tsx (dead components, 0 importers) и `.ltw-text-muted` (dead utility class) — отдельная cleanup-задача.
3. **Hover-state UX decision** для 3 interactive usages (аудит рекомендовал `&:hover { color: var(--mac-text-secondary); }`) — UX modification, вне canonical-token remediation scope.

**Process note — integrity incident & recovery:** между сессиями локальный клон оказался откатут к checkpoint (HEAD=e16f3b0c, 21 замена исчезла из worktree, локальные refs устарели). Remote подтверждён нетронутым на `69bdc9a9` (ls-remote + GitHub API). Recovery: discard байт-идентичной дубль-модификации plan-doc → чистый ff до `69bdc9a9` → повторное применение 21 замены → программное доказательство байт-идентичности diff → полный re-run gates (ratchet pre-edit 155/301 + post-edit 154/280, tsc, Vitest 1224/1224, build, bundle-check 0 residual). Задокументировано в worklog Task `2A-commit-gate`.

**CI verification (commit `9b1ef5d` на `origin/main`):** 33 check-runs, все terminal: 25 success + 8 skipped (expected для direct-main push: Load Tests k6, Staging readiness, PR Required Gate, Notify-on-failure ×2, Telegram Mini App Release Gate, DAST ZAP, Sentry source maps) + 0 failures. Regression Audit Gate ✅, Frontend e2e ✅, Frontend unit ✅, Frontend build ✅, Frontend lint ✅.

**Verification artifacts:** `/home/z/my-project/worklog.md` Task IDs `2A-text-muted-audit`, `2A-text-muted-remediation`, `2A-commit-gate`, `2A-push-ci`; evidence pack `/home/z/my-project/download/phase-2a-remediation-evidence-pack.md`; runtime proof `/home/z/my-project/download/phase-2a-runtime-proof.png`.

**STOP-AFTER-VERIFIED:** Phase 2A закрыта как VERIFIED. Phase 2B (`--mac-spacing-md` read-only semantic audit) НЕ запускается автоматически — требует отдельной команды пользователя.

### 4.1.5 Phase 2B-A — `--mac-spacing-md` Single-Usage Remediation (PR #2844, merge `26410a025`, 26.08.2026)

> Источник: Phase 2B undefined-token remediation, scenario A (user-approved): ровно один usage из 7. Публикация через branch + PR (MAIN INTEGRATION RULE; branch `fix/phase-2b-a-cardio-spacing-md` @ `9f853848`, base `fce3791`). **Status: VERIFIED (not merely MERGED)** — post-merge verification: merge-diff = ровно 1 файл +1/−1; CI merge commit terminal, 0 failures; ratchet prediction совпала бит-в-бит.

**Diff scope (exact):** 1 файл, +1/−1 — `frontend/src/pages/cardiology.css:64`: `gap: var(--mac-spacing-md)` → `gap: var(--mac-spacing-4)` (селектор `.cardio-flex-col`, cardiology settings-popover). Остальные 6 usage не тронуты; tokens.css / baseline / snapshots / Plan-SSOT не тронуты.

**Runtime proof (Playwright chromium, role=Doctor, `/doctor/cardiology?tab=visit`):** pre-fix — `--mac-spacing-md` не определён (var() без fallback → computed-value invalid → collapsed gap); post-fix — `rowGap = columnGap = 16px`; `--mac-spacing-4: 16px` (tokens.css:113) резолвится canonical.

**Metrics (ratchet, base `fce3791` → merge `26410a025`):** `undefinedVarNameCount` 154 → **154** (0); `undefinedVarUsages` 280 → **279** (−1); `varUsagesNoFallback` 11933 → **11933** (0). `--check` PASS (ниже потолков baseline 163/330/12003). Prediction аудита совпала бит-в-бит.

**CI:** branch `9f853848` — Tier-1 terminal: 18 success + 16 skipped, 0 failures (PR Review Quality Gate — после fix-in-PR PR-body по обязательному review-шаблону; код не менялся). Merge commit `26410a025` — 32 checks terminal: 25 success + 7 skipped, 0 failures.

**Остаток Phase 2B (deferred, отдельные команды пользователя):** 6 usage `var(--mac-spacing-md)` в cardiology.css (строки 70, 162, 225, 235, 236, 299).

**STOP-AFTER-VERIFIED:** Phase 2B-A закрыта как VERIFIED. Остаток Phase 2B и dead-code workstream НЕ запускаются автоматически — требуют отдельных команд пользователя.

### 4.1.6 PR-UI-09a — DataTable Foundation Remediation (PR #2843, merge `8143a361`, 26.08.2026)

> Источник: PR #2843 «refactor(ui): PR-UI-09a foundation remediation — canonical DataTable + macos/Table alias (zero-delta, re-do of closed #2842)», head `01a93de7` (branch `feat/ui-pr-09a-remediation-redo`), base `26410a025`; supersedes closed-not-merged #2842. SQUASH merge `8143a361` (single-parent, subject `(#2843)`), 26.08.2026 17:37:18Z, merged by drsapaev. **Status: MERGED-VERIFIED (post-merge audit: VERIFIED WITH DEFERRED ITEMS)** — merge-diff == PR-head diff бит-в-бит; `ui-baseline.json` НЕ тронут.

**Diff scope (exact): 12 файлов, +2006/−576:**

- `frontend/src/components/ui/DataTable.tsx` +891 — canonical DataTable (sticky header, sort, filter, pagination, selection, keyboard nav, density, skeleton/empty/error через features)
- `frontend/src/components/ui/macos/Table.tsx` +58/−573 → **61 LOC alias** (re-export canonical DataTable; обратная совместимость import-путей)
- `frontend/src/components/ui/DataTable-features/` ×5: TableEmpty 82, TableError 105, TablePagination 155, TableSkeleton 85, index 22
- `frontend/src/components/ui/__tests__/DataTable.test.tsx` +251
- `frontend/src/design-system/tokens.css` +191 — новые `mac-table-*` utility-классы
- `frontend/e2e/visual-regression.spec.ts` +166 / −3 + 2 новых snapshot PNG (registrar-eat-desktop, registrar-eat-mobile-scroll)

**Post-merge состояние таблиц (@ `8143a361`):** canonical `DataTable.tsx` 891 LOC; `macos/Table.tsx` 61 LOC alias. Живые consumers НЕ мигрированы (09c–09e): EnhancedAppointmentsTable 2282, common/Table 504, ResponsiveTable 468, RefundRequestsTable 431, QueueTable 239.

**Metrics (ratchet, base `26410a025` → merge `8143a361`):** `undefinedVarNameCount` 154 → **154** (0); `undefinedVarUsages` 279 → **281** (+2 — новые usage `var(--mac-bg-blue)` в добавленных `mac-table-*` классах tokens.css; токен уже был в undefined-списке → names не вырос); `varUsagesNoFallback` 11933 → **11969** (+36). `--check` PASS (ниже потолков baseline 163/330/12003).

**CI merge commit `8143a361`:** 34 checks, все terminal: 26 success + 8 skipped, 0 failures (Regression Audit Gate ✅, Frontend e2e ✅).

**Known follow-ups (deferred, отдельные решения пользователя, НЕ часть PR #2843):**

1. **`--mac-bg-blue` ×6 undefined usages** — DataTable.tsx ×4 (388, 393, 440, 450) + tokens.css ×2 (661, 663, `mac-table-*`). До PR #2843 — 4 usage (все в старом macos/Table.tsx); +2 drift от этого merge (см. Metrics). Токен не определён в canonical tokens.css: требуется canonical definition либо consumer-migration.
2. **PR-UI-09b–09e [09b RESOLVED → §4.1.7]:** 09b — decommission мёртвых Table-реализаций (ResponsiveTable, common/Table, ComponentTest): открытый PR #2848 (27.08.2026, +1/−1267, 6 файлов; NOT MERGED на срез 27.08.2026); 09c–09e — миграция живых consumers (EnhancedAppointmentsTable, RefundRequestsTable, QueueTable) на canonical DataTable.
3. **Visual-e2e governance note (историческая, НЕ кодовая регрессия):** registrar-eat-mobile-scroll visual e2e падал на pre-merge head `d1651792` PR #2843 (12328 px / 5%) и на main `f2de831e` (бит-в-бит та же сигнатура). Forensic-анализ (артефакты + рендер-пути): timing-зависимое async-состояние страницы на фиксированной точке capture (test-design fragility: waitForTimeout(3000) + lazy-load отделений + live ws-бейдж); каузальная связь с UI-audit коммитами отсутствует. Committed snapshot обновлён владельцем репо в PR #2847 (27.08.2026, PNG 76174 → 74750 bytes); Frontend e2e зелёный на `4b527766` и на срезе `1329342f` (33 checks, 0 failures).
4. **Branch hygiene:** `feat/ui-pr-09a-remediation-redo` не удалена на remote после merge.

**STOP-AFTER-VERIFIED:** PR-UI-09a закрыт как MERGED-VERIFIED. PR-UI-09b–09e и follow-ups НЕ запускаются автоматически — требуют отдельных команд пользователя.

### 4.1.7 PR-UI-09b — Decommission Dead Table Implementations (PR #2848, merge `11b423990`, 27.08.2026)

> Источник: PR #2848 «refactor(ui): PR-UI-09b — decommission dead Table implementations (responsive, common, ComponentTest) [Task 58 / PR-UI-09b]», head `24b548d9` (branch `feat/ui-pr-09b-decommission-dead-tables`), base `4b527766`; SQUASH merge `11b423990` (single-parent, subject `(#2848)`), 27.08.2026 14:39:03Z, merged by drsapaev. **Status: MERGED-VERIFIED (per §16: MERGED; VERIFIED — invariants 1–5 passed on merged main at `11b423990`; единственный DEFERRED — Codex review на #2848, 6-польная запись ниже, headline impact 0%).**

**Diff scope (exact): 6 файлов, +1/−1267 (3 DELETED, 3 modified):**

- `frontend/src/components/ResponsiveTable.tsx` — DELETED (−468; 0 живых импортов)
- `frontend/src/components/common/Table.tsx` — DELETED (−504; 0 живых импортов)
- `frontend/src/components/test/ComponentTest.tsx` — DELETED (−281; dev-only страница)
- `frontend/scripts/test-system.js` −5 (референсы удалённых компонентов)
- `frontend/src/components/common/index.ts` −1 (export удалённого Table)
- `frontend/src/utils/frontendAudit.tsx` +1/−8 (audit-manifest записи удалённых компонентов)

**Post-merge состояние таблиц (@ `11b423990`, переподтверждено на `b1ab98fa`):** canonical `DataTable.tsx` 891 LOC; `macos/Table.tsx` 61 LOC alias. Живые немигрированные standalone-реализации: EnhancedAppointmentsTable 2 282, RefundRequestsTable 431 (09c-1 — открытый PR #2857), QueueTable 239. Мёртвые (ResponsiveTable, common/Table, ComponentTest) удалены; 0 живых ссылок на удалённые файлы (остались только статические списки `ui-baseline.json` unreferencedFiles и комментарии в i18n locale-файлах).

**Metrics (ratchet, base `cded11b2` → merge `11b423990`; переподтверждено на `b1ab98fa`):** `undefinedVarNameCount` 154 → **154** (0); `undefinedVarUsages` 281 → **281** (0); `varUsagesNoFallback` 11973 → **11917** (**−56** — все 56 no-fallback var() находились в удалённых мёртвых таблицах). `--check` PASS (ниже потолков baseline 163/330/12003). Baseline `ui-baseline.json` НЕ тронут; snapshots НЕ тронуты; 09a-остатки `--mac-spacing-md` ×6 (cardiology.css: 70, 162, 225, 235, 236, 299) и `--mac-bg-blue` ×6 (DataTable.tsx: 388, 393, 440, 450 + tokens.css: 661, 663) — без изменений.

**CI merge commit `11b423990`:** 35 checks, все terminal: 26 success + 9 skipped, 0 failures (Regression Audit Gate ✅, Frontend e2e ✅, Frontend unit tests ✅). На head `24b548d9` PR Review Quality Gate имеет 2 исторических FAIL-прогона (02:06Z, 02:11Z — до исправления PR body) и финальный SUCCESS-прогон (02:15Z); финальное состояние CI на head чистое.

**Codex — DEFERRED (6-польная запись per AGENTS_UI.md §13):**

1. **Original requirement:** Codex review на PR #2848 в рамках стандартного review-gate workstream (прецеденты: #2843, #2852, #2857, #2859).
2. **Reason:** Codex usage limit reached в момент PR (27.08.2026); review не запускался — 0 reviews (подтверждено fresh API: v1.6 pre-flight PHASE 4, v1.6 sync STEP 5).
3. **Evidence:** проверено — merge CI @ `11b423990`: 35 checks = 26 PASS + 9 SKIP, 0 FAIL (Regression Audit Gate ✅, Frontend e2e ✅, Frontend unit tests ✅); independent post-merge audit на merged tree (v1.6 pre-flight, fresh API + git): diff ровно 6 файлов +1/−1267, ratchet 11973 → 11917 (−56), 0 живых ссылок на удалённые файлы, baseline/snapshots не тронуты — дефектов не выявлено. НЕ проверено — Codex-ревью как таковое (не выполнялось).
4. **Owner / workstream:** Plan-SSOT governance — UI-audit workstream (оркестратор).
5. **Resume condition:** повторный вызов Codex review на #2848 (head `24b548d9`) после восстановления quota ЛИБО явное user-решение «Codex на #2848 не требуется».
6. **Impact on headline completion %:** 0% — deferral процессный (review coverage), не code-AC; все code-AC PR-UI-09b верифицированы независимо на merged tree (CI + post-merge audit).

**Main-advance attribution (срез v1.5 `1329342f` → срез v1.6 `b1ab98fa`; каждый PR приписан фактическому merge-коммиту):** `893b8179` (#2853 backend pg_dump/pg_restore PATH fix — disjoint) → `cded11b2` (#2854 backend R2 offsite backup — disjoint) → `11b423990` (PR-UI-09b, этот ledger) → `ce32bbf5` (#2855 auth ForgotPassword fix + comment-only правка `macos/Table.tsx` «post-#2841 → post-2841», LOC 61 без изменений — disjoint к UI-audit) → `97e7fa52` (#2856 ops runbook — disjoint к UI-audit) → `cbfbaf970` (Plan-SSOT v1.5 sync, PR #2852, docs-only) → `b1ab98fa` (#2858 backend backup retention — disjoint). Ratchet на каждом post-#2848 anchor (`ce32bbf5`, `97e7fa52`, `cbfbaf970`, `b1ab98fa`) = 154/281/11917 (перемерено, включая `ce32bbf5` в fix-цикле v1.6; backend/docs-drift ratchet не меняет).

**Known follow-ups (informational / future work, отдельные решения пользователя, НЕ часть PR #2848):**

1. **PR-UI-09c начат внешним исполнителем [09c RESOLVED → §4.1.8]:** 09c-1 RefundRequestsTable → canonical DataTable — открытый PR #2857 (создан 28.08.2026 02:02:20Z; head `30aacb907d` @ `feat/pr-ui-09c-1-refund-requests-table`; base main `cbfbaf970`; 3 файла +58/−3: `RefundRequestsTable.tsx` +4/−3 — alias-decoupling, прямой import canonical DataTable + типизация `DataTableColumn`; `visual-regression.spec.ts` +54 — refunds-visual baseline; 1 новый snapshot PNG `cashier-refunds-tab-chromium-linux`). CI @ head: 38 checks, 21 success + 17 skipped, 0 failures. Codex RAN: P1 inline (plaintext patient name в E2E-фикстуре — PII) адресован вторым коммитом `30aacb907d` (anonymize PII per AGENTS.md §PII); re-review не запускался. Mergeable=True. Lifecycle PR НЕ изменён этим sync.
2. **Остаток 09c после 09c-1 [09c RESOLVED → §4.1.8]:** 10 alias-потребителей canonical DataTable через `macos/Table` (TelegramManager, admin/ActivationSystem, admin/QueueCabinetManagement, admin/ReportsManager, admin/ServiceCatalog, admin/SystemManagement, admin/UserManagement, analytics/AIAnalytics, files/FileManager, notifications/EmailSMSManager; RefundRequestsTable мигрирует в 09c-1) + standalone: EnhancedAppointmentsTable 2 282 LOC (6 consumers), QueueTable 239 LOC (1 consumer + stories).
3. **Branch hygiene:** `feat/ui-pr-09b-decommission-dead-tables` не удалена на remote после merge.
4. **Статический список unreferencedFiles в `ui-baseline.json`** содержит устаревшие записи удалённых файлов (информационное; ratchet-гейт использует counts, не список).

**STOP-AFTER-VERIFIED:** PR-UI-09b закрыт как MERGED-VERIFIED. PR-UI-09c/09d/09e и follow-ups НЕ запускаются автоматически — требуют отдельных команд пользователя.

### 4.1.8 PR-UI-09c — Live-Consumer Migration to Canonical DataTable (4 инкремента: PR #2857/#2860/#2861/#2862, 28.08.2026)

> Источники (все SQUASH merge, single-parent, merged by drsapaev): **09c-1** — PR #2857 «refactor(ui): PR-UI-09c-1 — migrate RefundRequestsTable to canonical DataTable + refunds visual baseline», head `30aacb907d` @ `feat/pr-ui-09c-1-refund-requests-table`, merge `c8464c81` (05:14:08Z); **09c-2** — PR #2860 «refactor(ui): PR-UI-09c-2 — migrate QueueTable to canonical DataTable», head `8ea29f4076` @ `feat/pr-ui-09c-2-queue-table`, merge `e35df1f0` (07:29:39Z); **09c-3** — PR #2861 «refactor(ui): PR-UI-09c-3 — decouple 10 macos/Table alias consumers to canonical DataTable», head `7f3ce58512` @ `feat/pr-ui-09c-3-alias-decoupling`, merge `e17d261b` (07:53:32Z); **09c-4** — PR #2862 «refactor(ui): PR-UI-09c-4 — migrate EnhancedAppointmentsTable to canonical DataTable», head `6b880f963e` @ `feat/pr-ui-09c-4-enhanced-appointments-table`, merge `028ab397` (10:05:18Z). **Status: MERGED-VERIFIED (per §16: MERGED; VERIFIED — invariants 1–5 passed on merged main; терминальный инкремент-анкор `028ab397`, переподтверждено на `4228c32d`; единственный DEFERRED — Codex review на #2861: review-gate НЕ закрыт и НЕ учитывается как completed review coverage (per §13; 6-польная запись ниже с resume condition), headline impact 0% — completion % определяется code-AC и от review-покрытия не зависит).**

**Diff scope (exact):** 09c-1 — 3 файла +58/−3 (`RefundRequestsTable.tsx` +4/−3 — прямой import canonical DataTable + типизация `DataTableColumn`; `visual-regression.spec.ts` +54 — refunds-visual baseline; НОВЫЙ snapshot `cashier-refunds-tab-chromium-linux.png`). 09c-2 — 3 файла +206/−179 (`QueueTable.tsx` +132/−112 — миграция на canonical DataTable с `DataTableColumn<QueueTableEntry>[]`, все 4 внешних early-return state сохранены (selectDoctor / loading / queueNotFound / queueEmpty — verified на merged tree), called-row highlight через CSS `:has()`; `QueueTable.css` +59/−57; `QueueTable.stories.tsx` +15/−10). 09c-3 — 10 файлов +24/−23 (import-path + JSX rename `Table` → `DataTable` в 10 alias-consumer'ах: TelegramManager, admin/{ActivationSystem, QueueCabinetManagement, ReportsManager, ServiceCatalog, SystemManagement, UserManagement}, analytics/AIAnalytics, files/FileManager, notifications/EmailSMSManager; zero-delta by construction — barrel re-export `Table === DataTable`, идентичный инстанс компонента). 09c-4 — 4 файла +842/−997 (`EnhancedAppointmentsTable.tsx` +716/−994 — внутренний рефактор на canonical DataTable с `DataTableColumn<AppointmentRow>[]`, публичный props/behavior-контракт неизменен для всех 6 consumers (RegistrarPanel, registrar WelcomeView, Appointments, Dentist/Dermatologist/Cardiology panels — verified grep на merged tree); `EnhancedAppointmentsTable.css` +94 — `:has()`-маркеры + `.eat-cell--*`; `RegistrarPanel.tsx` +13/−1 — фикс ModernTabs refetch-flicker; `visual-regression.spec.ts` +19/−2 — deterministic readiness wait).

**Post-merge состояние таблиц (@ `4228c32d`, fresh git-замер):** canonical `DataTable.tsx` 891 LOC; `macos/Table.tsx` 61 LOC alias — **0 живых consumers** (живых import'ов нет; остались только barrel-export `ui/macos` + reference в `DataTable.test.tsx` — финальный alias-cleanup = отдельный PR per docstring); EnhancedAppointmentsTable **2 004** (было 2 282, −278); QueueTable 259 (было 239, +20); RefundRequestsTable 432. Целевые LOC из §3.5/§7 (~400 / ~100 / ~150) в 09c НЕ достигались — исполнение выбрало zero-delta alias-decoupling (09c-1/09c-3) и contract-preserving internal refactor (09c-2/09c-4) вместо LOC-сокращения; LOC-редукция остаётся future-work кандидатом (см. follow-ups).

**Metrics (ratchet, fresh замер на каждом anchor, git archive read-only; хронологический порядок):** `c8464c81` (09c-1) 154/281/**11917** (0 к срезу v1.6 `b1ab98fa` 154/281/11917 — TSX import change only) → `0f94c005` (Plan-SSOT v1.6 docs-merge; docs-only, ratchet без изменений) 154/281/**11917** → `e35df1f0` (09c-2) 154/281/**11889** (−28 — QueueTable inline-стили → CSS-классы) → `e17d261b` (09c-3) 154/281/**11889** (0 — pure import decoupling) → `028ab397` (09c-4) 154/281/**11855** (−34 — EAT inline td/th → token CSS) → `4228c32d` (main) 154/281/**11855** (0 — drift #2863/#2864 auth-only). `--check` PASS на всех anchor'ах (ниже потолков baseline 163/330/12003). names/usages 154/281 — без изменений весь 09c. Baseline `ui-baseline.json` НЕ тронут (163/330/12003; последний commit baseline — #2835 `b5f95865`); snapshots: +1 новый (cashier-refunds-tab, 09c-1), EAT-snapshots НЕ менялись (zero-delta).

**CI (terminal, на merge-коммитах):** `c8464c81` 34 checks = 26 success + 8 skipped, 0 failures; `e35df1f0` 33 checks = 25 + 8, 0 failures; `e17d261b` 33 checks = 25 + 8, 0 failures; `028ab397` 34 checks = 26 + 8, 0 failures (Frontend e2e ✅); main `4228c32d` 33 checks = 25 + 8, 0 failures.

**Codex findings — disposition (fresh API, все inline-комментарии проверены):**

- **#2857 (09c-1):** P1 (plaintext patient name в E2E-фикстуре — PII) → FIXED вторым коммитом `30aacb907d` (anonymize PII per AGENTS.md §PII); re-review не запускался.
- **#2860 (09c-2):** P2 ×2 (called-row highlight vs DataTable inline styles; legacy cell padding в render-wrappers) → FIXED коммитом `1f41c060bb`; P1 (полные фамилии в story-фикстурах) → FIXED коммитом `8ea29f4076` (замена на инициалы; verified — «Тестов/Тестова» в stories на merged main отсутствуют).
- **#2861 (09c-3):** Codex review НЕ запускался (0 reviews) — DEFERRED, 6-польная запись ниже.
- **#2862 (09c-4):** P2 ×4 (checkbox key events активируют row; striped background после row hover; hide address column on mobile; row activation без onRowClick) → ALL FIXED: 3 шт. коммитом `113fd2a964`, 1 шт. (row activation) коммитом `6b880f963e`. P1 «Rebaseline the EAT screenshots after changing readiness» (09:46:02Z @ final head `6b880f963e`) → **REFUTED by evidence:** merge CI на `028ab397` — 34 checks terminal, 0 failures, включая Frontend e2e ✅; deterministic readiness wait (waitFor department tabs + table visible с catch-fallback) устранил race (12328 px diff от Vite dev-server cold transform), существующие baseline-снапшоты проходят без rebaseline.

**Codex — DEFERRED (6-польная запись per AGENTS_UI.md §13):**

1. **Original requirement:** Codex review на PR #2861 в рамках стандартного review-gate workstream (прецеденты: #2843, #2852, #2857, #2859, #2860, #2862).
2. **Reason:** Codex на #2861 не запускался — 0 reviews (verified fresh API); единственный инкремент 09c без Codex-прогона.
3. **Evidence:** проверено — merge CI @ `e17d261b`: 33 checks = 25 PASS + 8 SKIP, 0 FAIL; zero-delta by construction (barrel re-export `Table === DataTable` — идентичный инстанс компонента, tsc PASS); последующие инкременты (09c-4 `028ab397`) и main `4228c32d` CI green на дереве, включающем 09c-3; ratchet 11889 без изменений. НЕ проверено — Codex-ревью как таковое (не выполнялось).
4. **Owner / workstream:** Plan-SSOT governance — UI-audit workstream (оркестратор).
5. **Resume condition:** повторный вызов Codex review на #2861 (head `7f3ce58512`) ЛИБО явное user-решение «Codex на #2861 не требуется».
6. **Impact on headline completion %:** 0% — deferral процессный (review coverage), не code-AC; review-gate на #2861 остаётся ОТКРЫТЫМ и НЕ учитывается как completed review coverage (per §13: DEFERRED ≠ completed coverage) до выполнения resume condition; code-AC 09c (zero-delta-by-construction) верифицированы независимо на merged tree (CI + post-merge аудит), headline completion % определяется code-AC и от review-покрытия не зависит.

**EAT visual-proof nuance (по результатам аудита #2862):** DOM-probe доказал, что registrar-EAT baseline-поверхности НЕ монтируют таблицу в используемом baseline-сценарии (`tableCount: 0` — EAT рендерится только при `appointmentsLoading || filteredAppointments.length > 0`, а spec мокает `/registrar/queues/today` пустыми очередями). Поэтому 9/9 visual surfaces PASS НЕ является полноценным visual proof EAT; реальный EAT rendering проверен A/B DOM-probe на идентичных мок-данных (stash старой EAT vs новой): 12/12 содержимых ячеек, заголовки колонок, фон header'а и 1400px min-width layout — бит-в-бит идентичны; единственные intentional-дельты: canonical cell density (padding 12px 8px → 10px 16px) + `mac-table-scroll-wrapper` контейнер.

**ModernTabs refetch-flicker fix (pre-existing bug, surfaced в 09c-4):** найден и исправлен существовавший refetch-цикл на registrar-странице: inline `onProfilesLoaded` получал новую identity на каждый рендер RegistrarPanel → `loadQueueProfiles` (useCallback) пересоздавался → effect перезапускался → fetch → setState → рендер → повтор (бесконечный load → loaded → load flicker + неограниченный API refetch loop). Фикс: стабильный identity через `useCallback` с пустыми deps (коммит `5ff11c0dff`, `RegistrarPanel.tsx:221` — комментарий фиксирует root cause). Surfaced through visual-regression Surface 4 timing race (12328 px diff).

**Ratchet hex-regex false positive (resolved, historical):** tsxHex-метрика ui-baseline ratchet распознавала «PR #2860» (номер PR в prose-комментариях к QueueTable 09c-2 миграции) как hex-literal: +2 tsxHex → Regression Audit Gate FAIL на merge-коммите (373 → 374; независимо +1 hex добавил upstream #2863 в ResetPasswordPage.tsx — ratchet флагует сумму). Исправлено переформулировкой «#2860» → «PR-2860» (коммит `de9a8de62b`, comments-only, zero functional change; branch tsxHex назад к 371 — baseline-level, 0 net additions от PR). Проблема устранена; возможный фикс самого hex-regex в ui-baseline.mjs — informational/future-work, отдельный PR не требуется.

**Main-advance attribution (срез v1.6 `b1ab98fa` → срез v1.7 `4228c32d`; каждый PR приписан фактическому merge-коммиту, хронологический порядок):** `c8464c81` (09c-1 RefundRequestsTable, PR #2857 — этот workstream; merge 05:14:08Z — за ~12 минут ДО v1.6-merge 05:26:23Z, `0f94c005^ == c8464c81`; поэтому time-boxed запись v1.6 «09c-1 = открытый PR #2857» была корректной на срезе `b1ab98fa` и устарела к моменту merge v1.6) → `0f94c005` (Plan-SSOT v1.6 sync, PR #2859, docs-only) → `e35df1f0` (09c-2 QueueTable, PR #2860 — этот workstream) → `e17d261b` (09c-3 alias-decoupling, PR #2861 — этот workstream) → `3e44d0aa` (#2863 feat(auth) real /reset-password page — disjoint к UI-audit; независимо добавил +1 tsxHex, см. hex-regex note) → `028ab397` (09c-4 EnhancedAppointmentsTable, PR #2862 — этот workstream) → `4228c32d` (#2864 fix(auth) confirm-400 server detail — disjoint к UI-audit). Ratchet перемерен на каждом anchor (см. Metrics).

**Known follow-ups (informational / future work, отдельные решения пользователя, НЕ часть 09c):**

1. **09d–09e (остаток PR-UI-09) [09d + 09e-1 RESOLVED → §4.1.9]:** финальный alias-cleanup per docstring `macos/Table.tsx` — удаление 61-LOC alias + barrel-export после миграции последнего consumer (живых consumers уже 0; остались barrel-export `ui/macos` + reference в `DataTable.test.tsx`); завершение PR-UI-09 AC (см. §7).
2. **LOC-редукция таблиц:** целевые LOC из §3.5/§7 (EAT ~400, QueueTable ~100, RefundRequestsTable ~150) не достигнуты в 09c (фактически 2 004 / 259 / 432) — 09c выбрал zero-delta / contract-preserving путь; редукция — future-work кандидат в рамках 09d–09e или отдельных решений.
3. **Branch hygiene:** ветки `feat/pr-ui-09c-1..4`, `docs/plan-ssot-v1.6-sync` не удалены на remote после merge; дополнение v1.8: + `docs/plan-ssot-v1.7-sync`, `feat/pr-ui-09d-table-alias-cleanup`, `feat/pr-ui-09e-1-datatable-virtualization`.
4. **Статический список unreferencedFiles в `ui-baseline.json`** содержит устаревшие записи (информационное; ratchet-гейт использует counts, не список).

**STOP-AFTER-VERIFIED:** PR-UI-09c закрыт как MERGED-VERIFIED (4 инкремента). PR-UI-09d/09e и follow-ups НЕ запускаются автоматически — требуют отдельных команд пользователя.

### 4.1.9 PR-UI-09d + PR-UI-09e-1 — завершение PR-UI-09; старт Sprint 4 (PR #2870/#2872 + соседние #2867/#2869/#2871/#2873, 28.08.2026)

**PR-UI-09d — final alias-cleanup (PR #2870 → squash merge `7243a108`):**

- **Scope (6 файлов, +19/−167):** DELETE `components/ui/macos/Table.tsx` (61-LOC alias; живых consumers = 0 с 09c-3); DELETE `MacOSTable.test.tsx` (95 LOC, 6 тестов — дословные дубликаты DT-1..6 из 09a, стратегия задокументирована в §4.1.6); REMOVE table-экспорта из `ui/macos` barrel с removal-note; SYNC устаревших migration-path комментариев (`DataTable.tsx` header, `DataTable.test.tsx` docstring). Исторические provenance-комментарии в других местах намеренно сохранены.
- **Codex (head `96cd1782`):** 1 inline P2 — barrel лишился table-пути после удаления alias, removal-note рекламировала «(or via the ui/ barrel)». VALID; исправлено в-PR (commit `61a0e4c5`): `export { default as DataTable } from './DataTable'` в `ui/index.ts` + sync enumeration-комментария; proof — временный vitest-spec с import из barrel (удалён после проверки).
- **Validation:** tsc PASS; eslint 0 errors; vitest ui/ 41/41; check-theme PASS; audit:icon-controls 0 new; build PASS; ratchet 154/281/11855 `--check` PASS (identical — `__tests__` вне сканера); 0 `macos/Table` imports на staged tree; baseline 163/330/12003 не тронут.
- **Post-merge verification (10/10 PASS @ `7243a108`):** origin/main == squash SHA; single-parent; exact scope 6 файлов; AC на merged tree — 0 `macos/Table` imports, barrel Table export отсутствует, DataTable экспортирован из ui barrel, 1 canonical + 3 wrappers; CI merged main 33 checks 0 FAIL; ratchet идентичен; snapshots/baseline не в diff; worktree clean.

**PR-UI-09e-1 — DataTable row virtualization, PR-UI-09 AC4 (PR #2872 → squash merge `d20cde25`):**

- **Scope (6 commits, 2 файла, +378/−45):** `useVirtualizer` (overscan 10; getItemKey через стабильный getRowId per §C.4); правило активации `virtualized && numeric maxHeight` (bounded viewport — технически необходимый новый type-slot, задокументирован); measured geometry (data-index + measureElement на строках; rowHeight = initial estimate only); memoized callbacks (useCallback — устранён O(n) rebuild measurement cache на каждый scroll); `table-layout: fixed` + cell containment (overflow hidden, width); ARIA rowcount/rowindex (header/filter offset учтён); DT-13..16 (1000-row windowing + spacer math == totalSize; scroll re-ranging в хвост через scrollTop+scroll event; no-maxHeight явный fallback; estimate-40/measured-50 hybrid geometry). Все новые стили через helper-функции — inlineStyles ratchet неизменен.
- **Zero-delta proof:** A/B DOM dump 6 репрезентативных состояний (plain / selectable+sticky / loading / error / empty / pagination), branch vs main — IDENTICAL (0 bytes), повторено ×4 раунда по ходу review-цикла; 0 virtualized consumers на срезе (capability-only, AC4 delivered at component level).
- **Codex loop (4 раунда, 8 inline P2, каждый раунд триггерился body-PATCH):** 7 исправлены в-PR — row-height divergence (tr height = minimum → measured geometry), column shift under auto layout (→ fixed layout), measurement-cache identity (→ useCallback), ARIA row semantics, cell containment, prototype-mock cleanup no-op (test-only). P2-3 (roving-focus + scrollToIndex keyboard model для off-window строк) — **DEFERRED**, полная 6-полей запись в PR #2872 body; resume condition: первый интерактивный virtualized consumer или dedicated a11y-increment.
- **Validation:** tsc PASS; eslint 0 errors; vitest ui/ 45/45 (DT-1..16); check-theme PASS; build PASS; ratchet 154/281/11855 `--check` PASS на каждом head; baseline не тронут.
- **Post-merge verification (10/10 PASS @ `d20cde25`):** exact scope 2 файла; CI merged main 33 checks 0 FAIL; ratchet merged main 156/282/11883 `--check` PASS — дельта +2 names/+1 usages/+28 noFallback полностью атрибутирована PR-UI-11-1 (#2871: замер на `1378d6ef` = уже 156/282/11883, до merge 09e-1); вклад 09e-1 = 0; baseline/snapshots не в diff; worktree clean.

**Sprint-4 старт — соседние workstreams (repository evidence; fresh API+git верификация 28–29.08):**

- **PR-UI-10 (PR #2867 → squash `865ab5d8`, 13 файлов +171/−51; follow-up PR #2869 → squash `66c7ceff` — legacy brand-имена в brand.ts JSDoc):** верифицировано на main — `public/brand/{logo.svg,logo-mark.svg}` созданы; `brand.ts` name/shortName = 'Clinic OS'; 0 упоминаний «MediClinic Pro» в src (fresh grep 29.08). → **PR-UI-10 ✅ DONE.**
- **PR-UI-11-1 (PR #2871 → squash `1378d6ef`, 10 файлов +1359/−151):** AdminDashboard data-first (+673), canonical `DataCard.tsx` (+249) + `DataCard.test.tsx` (+163), i18n uz-Latn (+36) и др. Единственный источник ratchet-прироста этого sync-периода (см. выше).
- **PR-UI-11-2 (PR #2873 → squash `32edbc20`, 6 файлов +18/−18):** 6 admin MacOSCard consumers → canonical Card (AdminAppointments, AdminDoctors, AdminPatients, ServiceForm + 2).
- **PR-UI-11 остаток:** `MacOSCard` жив в **61 файле** (fresh grep 29.08, main `ad2f44ac`) — миграция consumers продолжается; PR-UI-06 остаётся ⚠️ PARTIAL до её завершения (canonical-стратегия Card/StatCard/DataCard создана).
- **Drift вне UI-audit workstream:** #2874 fix(jobs) — periodic lab/backup jobs в worker threads → `ad2f44ac` (backend, disjoint, ratchet 0).

**Known follow-ups (informational / future work, НЕ часть этого sync):**

1. **09e-2 LOC-редукция таблиц — ФОРМАЛЬНАЯ DEFERRED-запись (deferral-gate AGENTS_UI §13; закрывает P1 Codex #2875):**
   - **Original requirement:** PR-UI-09 AC2 «EnhancedAppointmentsTable ≤ 400 LOC» (+ цели §3.5/§7: QueueTable ≤ ~100, RefundRequestsTable ≤ ~150).
   - **Reason:** 09-серия выполняла zero-delta / contract-preserving миграцию (6 живых EAT-consumers, публичный контракт неизменён); LOC-редукция требует архитектурных решений (API/ownership, возможно clinical workflow) и явно выведена в отдельное решение пользователя (fast-autonomous directive: «НЕ начинай большую LOC-reduction автоматически»).
   - **Evidence:** LOC @ `d20cde25`: EAT 2 004 (снижен с 2 282 в 09c-4), QueueTable 259, RRT 432; ratchet-вклад 09-серии — §4.1.6–4.1.9; A/B DOM zero-delta ×4; **read-only architectural assessment ВЫПОЛНЕН (срез `faace538`, см. §4.1.10): безопасного автономного кандидата НЕТ — все три варианта требуют архитектурного решения.**
   - **Owner/workstream:** 09e-2 — не начат; исполнение только после явного решения пользователя.
   - **Resume condition:** пользователь одобряет наименьший безопасный extraction-кандидат по итогам assessment (mechanical cleanup с очевидным behavior preservation — допустимо автономно; изменение API/ownership/clinical workflow — отдельное архитектурное решение, STOP).
   - **Headline impact:** 8 SP PR-UI-09 исключены из headline completion до доставки 09e-2 (AGENTS_UI §13: DEFERRED ≠ completed coverage): portfolio v1.8 = полностью 9/19 PR, 37/103 SP; ratchet-метрики не затронуты; UI-поведение потребителей неизменно.
2. **Roving-focus DEFERRED** (PR #2872 body, 6 полей) — resume: первый интерактивный virtualized consumer или dedicated a11y-increment.
3. **Branch hygiene:** `feat/pr-ui-09c-1..4`, `docs/plan-ssot-v1.5/6/7-sync`, `feat/pr-ui-09d-table-alias-cleanup`, `feat/pr-ui-09e-1-datatable-virtualization` — удаление после завершения активной разработки (priority 4).
4. **C-6 nav-i18n gap** — впервые получил владельца: NEW PR-UI-19 (см. §7); полная матрица coverage — Приложение C.
5. **H-3 divergent ruling** (emr-tokens.css KEEP в §3 vs audit-fix «выразить через --mac-*»; dark-only `:root`-палитра жива) — зафиксирован в Приложении C; кандидат явного решения в Sprint 5 (EMR-секции).

### 4.1.10 PR-UI-12 COMPLETE + PR-UI-19 + PR-UI-11-3..12 — закрытие Sprint 4 (29.08.2026, срез main `64f73d40`)

**PR-UI-12 — все 4 пункта плана закрыты 4 инкрементами:**

- **12-1 DataTable UX feature layer (PR #2885 → squash `4199b9c2`, 10 файлов +1454/−33):** sticky filters (measured offset: headerRowHeight через useLayoutEffect + ResizeObserver — исправлен до этого «конфликт top: обе строки sticky top:0 перекрывались»), column-visibility toolbar (inert labels, last-column lock, Escape focus-restore, disclosure ARIA), density toggle (aria-pressed), roving keyboard nav (ArrowUp/Down/Home/End, single tabIndex, focus-restore-on-unmount, virtualized off-window tab-stop). Codex: 7 раундов, 15 находок — 14 fixed + 1 DEFERRED (visibilityLabel для non-string titles; resume: первый consumer с non-string title + toolbar). 28 новых DT-тестов (DT-17..44).
- **12-2 QueueTable roving keyboard nav (PR #2890 → squash `f4d577d7`, 2 файла +147):** §18-divergence разрешена по AGENTS_UI workflow step 4 — план «Enter для вызова пациента» vs QueueManager.contract.test.tsx «call-next = backend-owned command, not row command»: docs drift, repo-инвариант выиграл; rows = roving focus only. 1 refuted (Codex P1 «plaintext phone fixture» — доказано отсутствием такого правила; repo-конвенция fake-чисел), 1 DEFERRED (focus flash при background refresh — pre-existing loading-дизайн useQueueManager, owner: queue workstream).
- **12-3 EMR section skeleton loading (PR #2891 → squash `26347af3`, 9 файлов +240/−1):** EMRSectionSkeleton (6 карточек секций, role=status + aria-live=polite, prefers-reduced-motion отключает pulse); ветка строго `isLoading && !data` — ТОЛЬКО первая загрузка (autosave/refresh не подменяют живой ввод врача скелетом); EMRHookResult-интерфейс дополнен isLoading. Codex NOT RUN (0 reviews — не blocker, задокументировано).
- **12-4 Sticky table headers + visual regression AC (PR #2893 → squash `64f73d40`, 13 файлов +790/−6):**
  - **Kit:** `stickyHeader + maxHeight` (plain path) → bounded scroll viewport (`overflow-y:auto; max-height` на `.mac-table-scroll-wrapper`, тот же механизм что virtualized path; virtualization precedence сохранён; zero-delta без обоих флагов — DT-45/45b/45c). Sticky-оффсеты остаются MEASURED (никаких hardcoded top).
  - **Surfaces:** QueueTable `stickyHeader + maxHeight=480` (named constant), EAT `stickyHeader + maxHeight=560` — применено на 2 из 5 экранов AC, несущих таблицы; EMR/Patients(/clinical/search)/Lab на main таблиц НЕ имеют (формы/карточки/карточки) — ничего не вешалось, zero-delta.
  - **Pre-existing dead-prop fix:** Appointments.tsx передавал строки в EAT через legacy `appointments`-prop, который EAT декларирует, но НИКОГДА не деструктурирует (canonical = `data`, все прочие consumers его и передают) → тумблер «Расширенная таблица» ВСЕГДА рендерил пустую таблицу. Исправлено `data={filtered}` (+ dead-пропы appointmentsSelected/setAppointmentsSelected/updateAppointmentStatus/setShowWizard не тронуты — cleanup-кандидат).
  - **Visual regression AC:** 5 новых e2e-тестов (все API замоканы, PII-compliant фикстуры); Queue/Appointments несут DOM-level sticky-proof (после полного скролла viewport верх header == верх viewport, <1.5px); 5 NEW baseline'ов снято однократно; ВСЕ 9 существующих baseline'ов проходят UNCHANGED (registrar-eat desktop/mobile включительно — at-rest zero-delta A/B-доказательство).
  - **Validation:** vitest 1328/1328 (+11: DT-45..47, QueueTable.sticky ×3, EAT source-contract ×3); tsc/eslint/build/check-theme/icon-controls PASS; ratchet 156/282/11883 (вклад 0); CI head 38/38 + merged main 36/36, 0 failed. Codex NOT RUN (usage limit — задокументировано).

**PR-UI-19 — Navigation i18n, C-6 закрыт (PR #2879 → squash `faace538`, 12 файлов +776/−108):** 67 label → labelKey (45 nav.*-ключей) + 39 section → sectionKey + AI-disclaimer i18n; 51 ключ × 5 локалей (ru byte-identical — программно верифицировано 45/45; uz-Cyrl реальные переводы; kk medical-draft wording исправлен: «Қаралған» = «проверено», safety-значимо); CommandPalette локализованный поиск; реактивное переключение языка без reload. Codex: 3 раунда, 7 inline P2 — все VALID, все fixed (вкл. внесённую R1 регрессию интерливинга секций — поймана regression-guard тестом).

**PR-UI-11-3..11-12 (соседний workstream):** 10 инкрементов MacOSCard→Card (#2876/#2878/#2880/#2882/#2884/#2886/#2888/#2889/#2892/#2894) — потребители 61 → 12 файлов; каждый squash-merge VERIFIED (CI terminal, ratchet 0). PR-UI-11 остаётся 🟡 IN PROGRESS до 0 файлов.

**09e-2 read-only assessment (выполнен на `faace538`, закрывает Evidence-поле DEFERRED-записи §4.1.9):**

- **EAT (2 004 LOC):** god-таблица, 6 runtime consumers + contract-тест + csv/aggregation utils; редукция = декомпозиция по registrar-образцу (hooks + view-компоненты, серия PR) при сохранении публичного контракта — КРУПНОЕ архитектурное решение.
- **RRT (432 LOC):** CONTAINER, не таблица — владеет fetch + refund business-actions (approve/reject POST); редукция = перенос ownership в hook — изменение business-logic surface.
- **QueueTable (259 LOC):** уже thin DataTable-wrapper; цель ~100 достижима только косметическим file-split — 0 системной ценности; рекомендация — признать цель §3.5 устаревшей post-09c.
- **VERDICT: безопасного автономного кандидата НЕТ. Варианты для решения пользователя: (A) EAT-декомпозиция — multi-PR программа; (B) RRT container→useRefundRequests hook + presentational RRT; (C) QueueTable leave-as-is + docs-поправка §3.5; (D) полный defer в Sprint 5+.**

**Sprint-5 преамбула: все оставшиеся implementation-items (PR-UI-13/14/15) — god-panel decomposition того же архитектурного класса (RegistrarPanel 2 240 / CashierPanel 2 125 / Doctor+Dentist panels + EAT-декомпозиция) и НЕ начинаются автономно без явного решения о порядке/подходе (§4.2 порядок Admin→Registrar→Doctor→Cashier уже зафиксирован планом; решение = подтверждение старта и выбранного подхода).**

**Новые findings (12-4, informational / требуют решений — НЕ авто-фиксы):**

1. **Appointments.tsx RoleGate/ROLE_ALIASES divergence:** route registry допускает `Receptionist` на /clinical/appointments (через ROLE_ALIASES → registrar, P-014 widening), но page-level `<RoleGate roles={['Admin','Registrar','Doctor']}>` алиасы НЕ применяет → профиль с ролью `Receptionist` получает deny. Business-решение: расширить RoleGate алиасами (или включить 'Receptionist' в список) vs считать deny корректным поведением. Поверхностно мелкий фикс, но меняет фактический доступ к экрану — не выполнялся автономно.
2. **EAT dead props** (`appointments`, `appointmentsSelected`, `setAppointmentsSelected`, `updateAppointmentStatus`, `setShowWizard` — декларированы, не деструктурируются): cleanup-кандидат в PR-UI-15 (EAT-декомпозиция) или отдельный мини-PR.
3. **Lab catalog bare-array contract:** `/lab/catalog/{units,analytes}` потребляются LabTemplateWorkbench как голые массивы (`catalogAnalytes.map`) — объект-обёртки роняют render-tree (поймано в e2e-моках 12-4; на бэкенде контракт уже массив — frontend-хрупкость, задокументирована в спеке).
4. **Sticky-архитектура (SSOT-знание для PR-UI-13..15):** page-level sticky невозможен под `.app-shell-grid`; canonical-паттерн = `stickyHeader + maxHeight` (bounded viewport) — уже в kit JSDoc + покрывается DT-45..47.

**Ratchet на срез v1.9 (`64f73d40`): 156/282/11883, gate PASS — идентичен v1.8** (вклад 11-3..12 / 19 / 12-1..4 = 0; атрибуция по инкрементам — см. §4.1.10 entries выше). Baseline 163/330/12003 не тронут; snapshots — только 5 NEW (12-4, new tests).

### 4.2. Порядок миграции ролей (обновлено)

Миграция ролей в Sprint 5 (PR-UI-13/14/15) выполняется в порядке: **Admin → Registrar → Doctor → Cashier → Lab → Specialties**.

| Роль | Почему в этом порядке |
|---|---|
| **Admin** (Sprint 1-4, разбросанно) | Самое широкое покрытие каноничных primitives (38 экранов). Миграция Admin первой проверяет, что primitives выдерживают разнообразие; если Button/Card/Table не покрывают admin-use-case, лучше узнать сейчас. |
| **Registrar** (PR-UI-13) | Максимальная нагрузка на Wizard (3 154 LOC god-компонент), PaymentManager, queue, patients, batch API. Проверяет, что primitives выдерживают сложные формы + многошаговые flow. |
| **Doctor** (PR-UI-15, swap с Cashier) | ДО Cashier, потому что Doctor даёт реальную клиническую нагрузку на EMR (медкарта, 16 секций), QueueTable (keyboard nav), Patient cards, specialty-routing. Это проверяет primitives на data-first сценарии — то, ради чего делается Medical Minimalism. |
| **Cashier** (PR-UI-14) | После Doctor, потому что Cashier переиспользует primitives, уже обкатанные на Doctor (DataTable из RefundRequestsTable ≈ QueueTable, PaymentManager уже мигрирован в Registrar). CashierPanel — 2 125 LOC god-компонент, но структурно проще RegistrarPanel. |
| **Lab** (Sprint 5, последний) | Компактная панель (815 LOC), использует уже знакомые primitives. |
| **Specialties** (cardio/derma/dentist, Sprint 5-6) | Последними, потому что требуют specialty-color как дополнительного сигнала. К этому моменту canonical primitives уже стабильны, и добавление specialty-tint не сломает архитектуру. |

---

## 5. P0: критические дефекты (4 PR)

> ⚠️ **Уточнение порядка (обновлено):** PR-UI-03 (Language switcher fix) можно запускать **до** PR-UI-01. Это изолированный 1 SP PR без dependencies — быстрое тестирование regression-gate workflow перед большой миграцией ThemeProvider. Рекомендуемый порядок запуска: **PR-UI-03 → PR-UI-01 → PR-UI-02 → PR-UI-04**.

### PR-UI-01 — Единый ThemeProvider

> **Статус: ✅ DONE — merged #2812 (23.08.2026).** `macosTheme.tsx` + `AccentPicker` удалены; runtime-ссылок 0 (остаточные grep-матчи — provenance-комментарии). Codex review: 3 итерации, все issues resolved.

**Приоритет:** P0 · **Effort:** 5 SP · **Dependencies:** — · **Sprint:** 1

**Проблема:** В `src/App.tsx:451-466` два ThemeProvider обёрнуты друг в друга:

```tsx
// App.tsx — ТЕКУЩИЙ КОД (ПЛОХО)
<MacOSThemeProvider>           {/* macosTheme.tsx, 177 LOC */}
  <ThemeProvider>              {/* ThemeContext.tsx, 661 LOC */}
    <AppProviders>
      <AppContent />
    </AppProviders>
  </ThemeProvider>
</MacOSThemeProvider>
```

`ThemeContext.tsx:333` dispatch'ит `colorSchemeChanged` event:
```tsx
window.dispatchEvent(new CustomEvent('colorSchemeChanged', { detail: colorScheme }));
```

`macosTheme.tsx:86` слушает его и перезаписывает `--mac-accent-blue`:
```tsx
window.addEventListener('colorSchemeChanged', syncModeFromTheme);
// Затем в useEffect:
root.style.setProperty('--mac-accent-blue', adaptiveAccent);
root.style.setProperty('--mac-accent-blue-500', adaptiveAccent);
root.style.setProperty('--mac-accent-blue-600', hoverAccent);
root.style.setProperty('--mac-accent-blue-700', activeAccent);
root.style.setProperty('--mac-accent-blue-hover', hoverAccent);
root.style.setProperty('--mac-accent-blue-active', activeAccent);
```

Это классический **dual-truth**: ThemeContext устанавливает `--mac-accent-blue = #007aff`, а MacOSThemeProvider через 50ms перезаписывает его на `adaptiveAccent` (зависит от выбранного accent: blue/purple/pink/red/orange/yellow/graphite). Если пользователь меняет accent, `--mac-accent-blue` перестаёт быть blue — это ломает все компоненты, которые используют `var(--mac-accent-blue)` expecting blue color.

**Решение:**

1. **Удалить** `src/theme/macosTheme.tsx` (177 LOC)
2. **Удалить** `src/App.tsx:15` импорт `MacOSThemeProvider` + строку 451 обёртку
3. **Удалить** `src/App.tsx:467` закрывающий тег
4. **Обновить** `src/App.tsx:449-469`:
```tsx
// ЦЕЛЕВОЙ КОД (ХОРОШО)
export default function App() {
  return (
    <ThemeProvider>
      <AppProviders>
        <AppContent />
        <ToastContainer ... />
        <SpeedInsights ... />
      </AppProviders>
    </ThemeProvider>
  );
}
```
5. **Удалить** из `ThemeContext.tsx:333-336` dispatch `colorSchemeChanged` event (больше никто не слушает)
6. **Удалить** из `colorScheme.ts:102-260` определения `vibrant`, `glass`, `gradient` (3 custom schemes)
7. **Обновить** `src/components/admin/ColorSchemeSelector.tsx:6,125` — заменить `useMacOSTheme()` на `useTheme()`; удалить выбор accent (8 accent names)
8. **Удалить** `src/components/ui/macos/AccentPicker.tsx` (используется только в ColorSchemeSelector)
9. **Обновить** тесты `src/theme/__tests__/macosTheme.test.tsx` + `src/pages/__tests__/UserProfile.test.tsx` + `src/pages/__tests__/Login.accessibility.test.tsx` — удалить обёртку `MacOSThemeProvider`

**Acceptance criteria:**
- ✅ `grep -r "MacOSThemeProvider\|useMacOSTheme" src/` возвращает 0 результатов
- ✅ `grep -r "colorSchemeChanged" src/` возвращает 0 результатов
- ✅ Все 314 unit-тестов зелёные
- ✅ Visual regression: light/dark тема переключается корректно на 5 ключевых экранах (Landing, Login, /admin, /registrar, /doctor)
- ✅ `npm run type-check` без ошибок
- ✅ `npm run lint:check` без ошибок

**Regression risks:**
- AccentPicker удалён — пользователи, которые выбрали не-blue accent, потеряют настройку. localStorage `ui.accent` станет мёртвым ключом. Добавить migration script, который удаляет этот ключ при первом заходе после деплоя.
- ColorSchemeSelector в admin/settings покажет только 3 опции (light/dark/auto) вместо 6. Это ожидаемое поведение.

---

### PR-UI-02 — Единый design-token source

> **PR-UI-02 — ✅ with legacy follow-up** — required token cleanup completed (#2814, 23.08.2026) except `tokens-legacy.ts`, whose remaining importer (ThemeContext.tsx) is explicitly deferred to PR-17 (см. §3.1).

**Приоритет:** P0 · **Effort:** 3 SP · **Dependencies:** PR-UI-01 · **Sprint:** 1

**Проблема:** Документация `frontend/DESIGN_SYSTEM.md` называет `unifiedTheme.js` единым источником, тогда как `frontend/DESIGN_SYSTEM_ENFORCEMENT.md` называет каноническим `components/ui/macos`. При этом фактически:
- `src/theme/macos-tokens.css` (677 LOC) — основные CSS-переменные
- `src/theme/tokens-legacy.ts` — TypeScript-токены для ThemeContext.getColor/getSpacing
- `src/styles/macos.css` (840 LOC) — переопределения для vibrant/glass/gradient
- `src/styles/theme.css` (578 LOC) — дополнительные переменные

Это 4 источника, которые могут рассинхронизироваться.

**Решение:**

1. **Создать** `src/design-system/tokens.css` (переименовать + очистить `macos-tokens.css`):
   - Удалить секции `[data-color-scheme="vibrant"]`, `[data-color-scheme="glass"]`, `[data-color-scheme="gradient"]` (строки 25-95 в `styles/macos.css`)
   - Оставить только `:root` (light) + `@media (prefers-color-scheme: dark)` (dark) + `.dark-theme` (explicit)
   - Удалить aliases `--bg-primary: var(--mac-bg-primary)` и т.п. (строки 14-27) — все consumers используют `--mac-*` напрямую
2. **Удалить** `src/theme/tokens-legacy.ts` (используется только в ThemeContext.getColor/getSpacing)
3. **Обновить** `src/contexts/ThemeContext.tsx`:
   - Удалить `import tokens, { colors as tokenColors } from '../theme/tokens-legacy'` (строка 12)
   - Удалить `getColor`, `getSpacing`, `getFontSize`, `getShadow` из контекста (строки 191-236)
   - Удалить `designTokens: typeof tokens` из `ThemeContextValue` (строка 65)
   - Компоненты должны использовать CSS-переменные напрямую через `var(--mac-accent-blue)`, а не `getColor('primary', 500)`
4. **Обновить** `src/App.tsx:8-14` импорты:
   ```tsx
   import './styles/theme.css';                    // удалить (дублирует tokens.css)
   import './styles/dark-theme-visibility-fix.css'; // оставить
   import './styles/global-fixes.css';              // оставить
   import './design-system/tokens.css';              // переименовать с './theme/macos-tokens.css'
   import './styles/macos.css';                     // оставить (но сократить после PR-UI-01)
   ```
5. **Обновить** `frontend/DESIGN_SYSTEM.md` + `frontend/DESIGN_SYSTEM_ENFORCEMENT.md` — указать `src/design-system/tokens.css` как единственный canonical source
6. **Мигрировать** потребителей `getColor()` / `getSpacing()` / `getFontSize()` / `getShadow()`:
   ```tsx
   // Было:
   const color = getColor('primary', 500);
   const padding = getSpacing('md');
   // Стало:
   const color = 'var(--mac-accent-blue)';
   const padding = 'var(--mac-spacing-4)';
   ```
   Греп: `grep -rn "getColor\|getSpacing\|getFontSize\|getShadow\|designTokens" src/` — найти все ~30 потребителей и мигрировать.

**Acceptance criteria:**
- ✅ `grep -r "tokens-legacy" src/` возвращает 0 результатов
- ✅ `grep -r "getColor\|getSpacing\|getFontSize\|getShadow" src/` возвращает 0 результатов в компонентах (только в самом ThemeContext если временно оставлено)
- ✅ `frontend/DESIGN_SYSTEM.md` указывает на `src/design-system/tokens.css`
- ✅ Light/dark тема работает на всех 12 ключевых экранах
- ✅ Visual regression: сравнение скриншотов до/после — pixel-diff < 5% (только переименования, без визуальных изменений)

**Regression risks:**
- Компоненты, использующие `getColor('primary', 500)` — получат другой цвет, если `tokens-legacy.ts` имел отличающиеся значения. Проверить через visual regression на 12 экранах.
- `designTokens` в ThemeContextValue — удалить из типа. Если TypeScript-ошибка в 30+ файлах — это нормально, исправить в этом же PR.

---

### PR-UI-03 — Фикс Language Switcher в UnifiedSidebar

> **Статус: ✅ DONE — merged #2810 + #2813 (23.08.2026).** UnifiedSidebar + UnifiedLayout + `unified-sidebar.css` + `sidebar-buttons.css` удалены ЗДЕСЬ (опережение плана: матрица относила UnifiedLayout/CSS к PR-08/PR-17). Deletion `cursor-effects.css` отложено на PR-17 (решение Codex review в #2810: 9 interaction-классов ещё потребляются MediLabDemo). Чеклист 10/10 пройден.

**Приоритет:** P0 · **Effort:** 1 SP · **Dependencies:** — · **Sprint:** 1

> ⚠️ **Можно выполнять ПЕРВЫМ, до PR-UI-01.** Это изолированный PR без dependencies, который (а) исправляет реальный функциональный баг, (б) проверяет regression-gate workflow перед более рискованными изменениями.

**Проблема:** `src/components/layout/UnifiedSidebar.tsx:31,74` содержит локальный `useState('en')` + toggle без вызова i18next:

```tsx
// UnifiedSidebar.tsx:31
const [language, setLanguage] = useState('en');

// UnifiedSidebar.tsx:73-75
const handleLanguageToggle = () => {
  setLanguage((prev) => prev === 'en' ? 'ru' : 'en');
};
```

Это означает, что кнопка меняет собственное состояние (EN → RU → EN), но остальные UI остаётся на прежнем языке. Пользователь думает, что сменил язык, но на самом деле — нет. **Это не стилистическая мелочь, а функциональная поломка** — подрывает доверие к интерфейсу.

Аналогичный баг в `src/components/LanguageSwitcher.tsx` уже **исправлен** в актуальном main (теперь использует `useTranslation().setLanguage(code)`), но UnifiedSidebar остался незамеченным.

**Решение:** Поскольку `UnifiedSidebar.tsx` используется только в `MediLabDemo.tsx` (demo-only, доступен только Admin при `VITE_ENABLE_INTERNAL_DEMO=1`), **удалить файл целиком** вместе с `UnifiedLayout.tsx`.

### ⚠️ UnifiedSidebar deletion checklist (10 пунктов — ОБЯЗАТЕЛЕН перед удалением)

Перед удалением `UnifiedSidebar.tsx` убедиться, что canonical `Sidebar` (из `src/components/ui/macos/Sidebar.tsx`) покрывает ВСЕ 10 функций UnifiedSidebar. Если хотя бы одна не покрыта — НЕ удалять UnifiedSidebar, пока не добавлена в canonical.

| # | Функция | Где проверить в canonical Sidebar | Acceptance criteria |
|---|---|---|---|
| 1 | Role filtering (RBAC-driven items) | `SIDEBAR_PRESETS[role]` → `routeSelectors.getRouteChromeState` | Все 9 ролей (Admin, Registrar, Doctor, Cashier, Lab, cardio/derma/dentist, Patient) получают корректный набор пунктов |
| 2 | Active route highlight | `activeItem` prop + `useLocation().pathname` matching | Текущий пункт подсвечен при прямой навигации и при reload страницы |
| 3 | Collapsed state (icon-only mode) | `collapsed`/`defaultCollapsed` props + localStorage persistence | Состояние сохраняется между сессиями; иконки видны в collapsed режиме |
| 4 | Mobile behavior (overlay drawer) | `App.tsx:246-322` mobile-sidebar logic (после PR-UI-04 — overlay drawer pattern) | На 375px viewport sidebar скрыт по умолчанию; hamburger открывает overlay |
| 5 | Theme toggle | `useTheme().toggleTheme()` из canonical ThemeContext | Клик переключает light↔dark↔auto; иконка обновляется мгновенно |
| 6 | Language switch | `useTranslation().language` + `setLanguage(code)` (**НЕ локальный useState!**) | Кнопка EN/RU/UZ синхронизирована с фактическим языком UI |
| 7 | Profile display (avatar + name) | `auth.getState().profile` + аватар (initials или изображение) | В collapsed режиме показывает только аватар с tooltip «Dr. Sapaev / Cardiologist» |
| 8 | Logout | `auth.clearToken()` + redirect на `/login` (через `useNavigate`) | После logout пользователь оказывается на `/login`, а не остаётся на текущей странице |
| 9 | Keyboard navigation | `tabIndex`, `aria-label`, `:focus-visible` outline на каждом пункте | Tab перемещает фокус по пунктам; Enter активирует; Escape закрывает overlay |
| 10 | ARIA (`aria-label`, `aria-current`, `role="navigation"`) | `aria-label="Главное меню"`, `aria-current="page"` на активном пункте | Screen reader озвучивает: «Главное меню, навигация, текущий раздел: Очередь» |

**Если canonical Sidebar не покрывает хотя бы одну функцию из списка — это блокер для PR-UI-03.** Сначала расширить canonical Sidebar в отдельном sub-PR (PR-UI-03a), прогнать regression-gate, и только потом удалять UnifiedSidebar в PR-UI-03b.

Если по какой-то причине удаление невозможно (например, демо-страница нужна для дизайн-ревью), то минимальный фикс:

```tsx
// UnifiedSidebar.tsx — МИНИМАЛЬНЫЙ ФИКС (если не удалять)
import { useTranslation } from '../../i18n/useTranslation';
// ...
// Удалить строку 31: const [language, setLanguage] = useState('en');

// Получать language из i18next:
const { language, setLanguage } = useTranslation();

// Обновить handleLanguageToggle (строка 73-75):
const handleLanguageToggle = () => {
  setLanguage(language === 'en' ? 'ru' : 'en');
};
```

Но рекомендуется именно удаление, потому что:
- UnifiedSidebar содержит ещё 4 проблемы (см. §3.2 file matrix)
- Используется только в demo-странице
- Миграция `MediLabDemo.tsx` на canonical `Sidebar` решает все проблемы сразу

**Действие:**
1. **Удалить** `src/components/layout/UnifiedSidebar.tsx` (498 LOC)
2. **Удалить** `src/components/layout/UnifiedLayout.tsx` (123 LOC)
3. **Обновить** `src/pages/MediLabDemo.tsx:8` — заменить импорт `UnifiedLayout` на canonical AppShell
4. **Обновить** `src/pages/MediLabDemo.tsx:773-775` — обернуть в AppShell с `data-demo="true"`
5. **Удалить** `src/styles/unified-sidebar.css` (302 LOC) — стили для удалённого компонента

**Acceptance criteria:**
- ✅ Все 10 пунктов UnifiedSidebar deletion checklist пройдены (canonical Sidebar покрывает все функции)
- ✅ `grep -r "UnifiedSidebar\|UnifiedLayout" src/` возвращает 0 результатов
- ✅ `grep -rn "useState.*['\"]en['\"]\|setLanguage(prev" src/` возвращает 0 результатов
- ✅ `MediLabDemo` страница открывается на `/internal-demo/medilab` (только при `VITE_ENABLE_INTERNAL_DEMO=1`)
- ✅ Language switcher в `/internal-demo/medilab` корректно меняет язык всех UI элементов
- ✅ Добавить regression-тест: проверка что `useTranslation().language` синхронизирован с UI кнопкой

**Regression risks:**
- Минимальные: демо-страница не используется в продакшене. Если что-то сломается — заметят только админы при включении demo-mode.
- Если canonical Sidebar не покрывает какую-то из 10 функций — расширить canonical Sidebar ПЕРЕД удалением UnifiedSidebar.

---

### PR-UI-04 — Единый AppShell + Navigation

> **PR-UI-04 — ✅ with legacy naming follow-up** — AppShell work completed (#2815 + 04a #2816 + 04b #2817, 23.08.2026); `ModernTabs → Tabs` rename remains deferred to PR-17 (см. §3.2).

**Приоритет:** P0 · **Effort:** 8 SP · **Dependencies:** PR-UI-01, PR-UI-02 · **Sprint:** 2

**Проблема:** Три разные модели навигации для разных ролей:

| Роль | Текущая навигация | Где реализовано |
|---|---|---|
| Admin | Sidebar (canonical macOS Sidebar) | `SIDEBAR_PRESETS.admin` в routeRegistry |
| Doctor | Sidebar (canonical) | `SIDEBAR_PRESETS.doctor` |
| Lab | Sidebar (canonical) | `SIDEBAR_PRESETS.lab` |
| Cardio/Derma/Dentist | Sidebar (canonical, query-param based) | `SIDEBAR_PRESETS.cardiology/dermatology/dentistry` |
| Registrar | Header tabs (hardcoded) + ModernTabs в теле страницы | `HeaderNew.tsx:120+` |
| Cashier | Header "Касса" button + ModernTabs в теле страницы | `HeaderNew.tsx` + `CashierPanel.tsx` |
| Patient | TelegramMiniAppPatientShell (отдельная поверхность) | `TelegramMiniAppPatientShell.tsx` |

Это означает: пользователь с правами Admin+Registrar видит две разные модели навигации на двух разных экранах. Это нарушение принципа единого UX.

`routeRegistry.ts:42-48` содержит комментарий P-016:
```ts
// P-016 fix: removed the `registrar`, `patient`, and `cashier` presets —
// all routes that referenced them set hideSidebar:true, so the items below
// were never rendered. The actual navigation for these roles lives in:
//   - registrar: HeaderNew.jsx (hardcoded buttons) + ModernTabs in page body
//   - patient:   TelegramMiniAppPatientShell (separate surface, no sidebar)
//   - cashier:   HeaderNew.jsx (single "Касса" button) + tabs in CashierPanel
```

**Решение:**

1. **Восстановить** `SIDEBAR_PRESETS.registrar` и `SIDEBAR_PRESETS.cashier` в `routeRegistry.ts`:
```ts
// routeRegistry.ts — ДОБАВИТЬ
registrar: {
  navigation: 'path',
  defaultItem: 'registrar-home',
  items: [
    { id: 'registrar-home', label: 'Обзор', icon: 'chart.bar' },
    { id: 'registrar-queue', label: 'Очередь', icon: 'person.2' },
    { id: 'clinical-appointments', label: 'Записи', icon: 'calendar' },
    { id: 'clinical-search', label: 'Пациенты', icon: 'person.2' },
    { id: 'admin-finance', label: 'Финансы', icon: 'creditcard' },
  ],
},
cashier: {
  navigation: 'path',
  defaultItem: 'cashier-home',
  items: [
    { id: 'cashier-home', label: 'Касса', icon: 'creditcard' },
    { id: 'clinical-appointments', label: 'Записи', icon: 'calendar' },
    { id: 'admin-finance', label: 'Финансы', icon: 'chart.bar' },
  ],
},
```

2. **Обновить** `routeSelectors.ts` — `getRouteChromeState` возвращает sidebar preset для registrar/cashier на основе role

3. **Обновить** маршруты registrar/cashier в `routeRegistry.ts` — убрать `hideSidebar: true` (если есть):
```ts
// Было (для registrar-home):
{
  id: 'registrar-home',
  path: '/registrar',
  // ... hideSidebar: true  ← удалить если есть
}
```

4. **Удалить** из `HeaderNew.tsx` хардкод navigational buttons для registrar/cashier (строки 120+). Header содержит только: brand, GlobalSearchBar, NotificationCenter, profile menu, LanguageSwitcher, theme toggle. НЕ навигацию.

5. **Обновить** `RegistrarPanel.tsx:1486` — ModernTabs перепрофилировать с навигационной функции на контентную (переключение между Queue view / Welcome view / Appointments view внутри страницы, не между разделами). Переименовать ModernTabs в `Tabs`.

6. **Обновить** `CashierPanel.tsx` — аналогично, ModernTabs переключает внутри страницы (Pending / History / Refunds tabs), не между разделами.

7. **Удалить** дублирующую логику mobile-sidebar в `App.tsx:246-322` — использовать стандартный overlay-drawer pattern:
   - Mobile (< 768px): sidebar скрыт по умолчанию, hamburger открывает overlay drawer
   - Desktop (≥ 768px): sidebar виден, collapse-button сворачивает в icon-only (72px)
   - Удалить `mobileSidebarExpanded` state + `compactSidebar` ternary (строки 175-322)

**Acceptance criteria:**
- ✅ `grep -rn "hideSidebar.*true" src/routing/routeRegistry.ts` — нет для registrar/cashier/doctor/lab
- ✅ `grep -rn "ModernTabs.*navigation\|hardcoded.*button" src/components/layout/HeaderNew.tsx` — 0 результатов
- ✅ RegistrarPanel отображает canonical Sidebar слева, ModernTabs только для контентных табов внутри страницы
- ✅ CashierPanel — аналогично
- ✅ DoctorPanel, LabPanel, specialty panels — без изменений (уже canonical)
- ✅ Mobile (375px viewport): sidebar скрыт, hamburger открывает overlay drawer с полным меню
- ✅ Visual regression на 6 экранах: Landing, Login, /admin, /registrar, /doctor, /cashier

**Regression risks:**
- Пользователи registrar/cashier привыкли к header-tabs. После миграции — sidebar слева. Может потребоваться онбординг-баннер «Изменилась навигация».
- ModernTabs в RegistrarPanel теряет навигационную функцию — все использования `useSearchParams().get('tab')` для смены раздела нужно заменить на `useNavigate()`. ~10 мест.
- PatientPanel: оставить TelegramMiniAppPatientShell как отдельную поверхность (это Mini App для Telegram, не браузерный UI).

---

## 6. P1: primitives & state patterns (5 PR)

### PR-UI-05 — Унификация Button primitive

> **Статус: ✅ DONE — merged #2819 (23.08.2026) + supplemental P1a (25.08.2026).** Variants 11→6 завершены; P1a дополнительно мигрировал 32 non-canonical варианта на canonical API.

**Приоритет:** P1 · **Effort:** 3 SP · **Dependencies:** PR-UI-02 · **Sprint:** 2

**Проблема:** `src/components/ui/macos/Button.tsx:4` определяет variant как `string`, что позволяет 11+ значений:

```tsx
type ButtonVariant = 'default' | 'primary' | 'secondary' | 'success' | 'warning' |
                     'danger' | 'destructive' | 'error' | 'ghost' | 'outline' | 'link' | string;
```

6 из них семантически пересекаются (danger/destructive/error — одно и то же; success/warning визуально близки). В кодовой базе Button используется с 14 разными значениями variant (включая несуществующие в типе — например, `"icon"` в HeaderNew), потому что `string` не ловит опечатки.

**Решение:**

1. **Обновить** тип `ButtonVariant` в `Button.tsx:4`:
```tsx
// Было:
type ButtonVariant = 'default' | 'primary' | 'secondary' | 'success' | 'warning' |
                     'danger' | 'destructive' | 'error' | 'ghost' | 'outline' | 'link' | string;

// Стало:
type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'outline' | 'danger' | 'link';
```

2. **Удалить** из `variantStyles` (строки 101-161): `default` (→ `secondary`), `success` (→ `secondary` с color-prop), `warning` (→ `secondary` с color-prop), `destructive` (→ `danger`), `error` (→ `danger`)

3. **Добавить** опциональный prop `color?: 'default' | 'success' | 'warning' | 'danger'` для семантической окраски secondary variant

4. **Мигрировать** потребителей:
   ```bash
   # Найти все использования несуществующих variants
   grep -rn 'variant=["\x27]\(default\|success\|warning\|destructive\|error\|icon\)["\x27]' src/
   ```
   - `variant="default"` → `variant="secondary"`
   - `variant="success"` → `variant="secondary" color="success"`
   - `variant="warning"` → `variant="secondary" color="warning"`
   - `variant="destructive"` → `variant="danger"`
   - `variant="error"` → `variant="danger"`
   - `variant="icon"` → `variant="ghost"` + `size="small"` + `aria-label`

5. **Удалить** алиас `MacOSButton` если есть (его нет, но проверить после миграции)

**Acceptance criteria:**
- ✅ `tsc --noEmit` ловит неизвестные variant значения (поскольку `ButtonVariant` теперь literal-union)
- ✅ `grep -rn 'variant=["\x27]\(default\|success\|warning\|destructive\|error\|icon\)["\x27]' src/` — 0 результатов
- ✅ Visual regression: кнопки выглядят идентично (mapping сохранён)

---

### PR-UI-06 — 3 типа Card вместо 8

> **PR-UI-06 — ⚠️ PARTIAL / acceptance incomplete**
> Completed: `MacOSMetricCard`/`ModernCard` removal and `StatCard` migration (#2820, 23.08.2026).
> Remaining live legacy surface: `MacOSCard` (329 JSX consumers); canonical `DataCard` has not been introduced.
> Follow-up ownership: PR-UI-11 Dashboard. Do not classify as completed until the canonical card strategy is resolved.

**Приоритет:** P1 · **Effort:** 5 SP · **Dependencies:** PR-UI-02 · **Sprint:** 2

**Проблема:** 8 параллельных Card-типов в кодовой базе (см. §3.4). Цель: оставить 3 canonical:
- **Card** — контейнер для группировки
- **StatCard** — для метрик (Patients today / Revenue / Waiting / Appointments)
- **DataCard** — для queue / appointments / lab results (с заголовком + actions + body)

**Решение:**

1. **Обновить** `src/components/ui/macos/Card.tsx` — canonical `Card`. Удалить алиас `MacOSCard` (экспортировать только `Card`)

2. **Обновить** `src/components/ui/macos/MacOSStatCard.tsx` → переименовать файл в `src/components/ui/StatCard.tsx`. Объединить с `MacOSMetricCard` (удалить последний). 33 потребителя `MacOSMetricCard` мигрировать на `StatCard`.

3. **Создать** `src/components/ui/DataCard.tsx` — новый canonical для data-first cards:
```tsx
interface DataCardProps {
  title: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  accent?: 'default' | 'success' | 'warning' | 'danger';
  density?: 'compact' | 'comfortable';
}
```

4. **Удалить:**
   - `src/components/medical/MedicalCard.tsx` (мёртвый, только в MediLabDemo)
   - `src/components/medical/MetricCard.tsx` (мёртвый)
   - `src/components/medical/PatientCard.tsx` (мёртвый)
   - `src/components/layout/ModernCard.tsx` (0 импортов)

5. **Мигрировать** потребителей:
   - `MedicalCard` → `Card` (только в MediLabDemo)
   - `MetricCard` (medical) → `StatCard`
   - `PatientCard` (medical) → `DataCard`
   - `ModernCard` → `Card` (0 потребителей, но проверить косвенно)
   - `UnifiedCard` → `Card`
   - `MacOSCard` → `Card` (алиас)
   - `MacOSMetricCard` → `StatCard`
   - `StatCard` (если существует как separate) → `StatCard` (canonical)

6. **Обновить** `src/components/ui/macos/index.ts` — удалить экспорты удалённых компонентов

**Acceptance criteria:**
- ✅ `grep -rohE "ModernCard|MacOSCard|UnifiedCard|MetricCard|MedicalCard|MacOSMetricCard|MacOSStatCard|PatientCard" src/components --include="*.tsx"` — возвращает только canonical: `Card`, `StatCard`, `DataCard`
- ✅ 69 файлов-потребителей мигрированы
- ✅ Visual regression: карточки выглядят идентично

---

### PR-UI-07 — Loading / Empty / Error unified

> **Статус: ✅ DONE — #2823 (24.08.2026, phase 1: dead loading primitives) + серия 07a из 12 sub-PR (#2824–#2836, 24–25.08.2026).** Финал 8b (#2836): MacOSEmptyState физически декомиссионирован (файл + barrel-export + legacy-тест, −335 LOC). Runtime-упоминаний 0; 11 residual — комментарии (задокументированы).
>
> **Ledger серии PR-UI-07a:** 1a #2824 admin error states · 1b #2825 admin empty states · 2a #2826 admin type-prop · 2b #2827 admin iconStyle · 2c #2828 ReportsManager children→action (behavior fix) · 3a #2830 cardiology · 3b #2831 DoctorQueuePanel · 3c #2832 analytics · 3d #2833 dermatology · 4 #2834 StateWrapper (behavior fix) · 8a #2835 AppEmpty internalization · 8b #2836 decommission. Proof-of-safety: sandbox-симуляция dependency-graph перед 8b; tree identity head↔squash верифицирована при merge.

**Приоритет:** P1 · **Effort:** 5 SP · **Dependencies:** PR-UI-06 · **Sprint:** 3

**Проблема:** `AppState.tsx` (240 LOC) экспортирует `AppLoading`, `AppEmpty`, `AppError`. `MacOSEmptyState.tsx` (191 LOC) — дубликат `AppEmpty`. 33 потребителя используют `MacOSEmptyState`, 9 — `AppState`. Skeleton (188 LOC, 34 потребителя) — canonical.

**Решение:**

1. **Обновить** `src/components/ui/macos/AppState.tsx`:
   - Удалить импорт `MacOSEmptyState` (строка 3)
   - Внутренне `AppEmpty` использует собственный рендер (не `MacOSEmptyState`)
   - Добавить prop `action?: ReactNode` для CTA (например, "Register patient")

2. **Удалить** `src/components/ui/macos/MacOSEmptyState.tsx` (191 LOC)

3. **Мигрировать** 33 потребителя `MacOSEmptyState`:
```tsx
// Было:
<MacOSEmptyState
  title="Нет пациентов"
  description="Измените фильтры или зарегистрируйте нового"
  action={<Button>Регистрировать</Button>}
/>

// Стало:
<AppEmpty
  title="Пациенты не найдены"
  description="Измените фильтры или зарегистрируйте нового пациента"
  action={<Button variant="primary">Регистрировать пациента</Button>}
/>
```

4. **Стандартизировать** empty state texts по medical pattern:
   - ❌ "No data" → ✅ "Список пациентов пуст"
   - ❌ "Request failed" → ✅ "Не удалось загрузить список пациентов. Данные не потеряны. Попробуйте ещё раз."
   - ❌ "Loading..." → ✅ Skeleton rows для таблиц / Skeleton cards для dashboards

5. **Добавить** в `AppState.tsx` semantic icons для каждого состояния (lucide-react):
   - `AppLoading` → spinner (Loader2)
   - `AppEmpty` → Inbox / Search / UserPlus (по контексту)
   - `AppError` → AlertCircle / RefreshCw

6. **Создать** `src/components/ui/Skeleton patterns`:
   - `TableSkeleton` — skeleton rows для таблиц
   - `CardGridSkeleton` — skeleton cards для dashboards
   - `SectionSkeleton` — skeleton для EMR sections

**Acceptance criteria:**
- ✅ `grep -r "MacOSEmptyState" src/` — 0 результатов
- ✅ Все empty states содержат actionable CTA (button) + медицински понятный текст
- ✅ Loading ≠ empty (skeleton для loading, AppEmpty для empty)
- ✅ Visual regression: 5 экранов с loading/empty/error states

---

### PR-UI-08 — Убрать glass + лишние animation effects

> **Статус: ✅ DONE — merged #2838 (25.08.2026, squash `ae7236cb6`, parent `c9ea39edd`). 23 files, +85/−720.**
>
> **D1–D8 rulings (all applied):**
> - **D1** — `--mac-card-bg` translucent (rgba 0.88 light / 0.86 dark) KEPT; 118 consumers not perturbed. (Plan original "solid #FFFFFF/#1C1C1E" not applied — D1 ruling: do not change global token.)
> - **D2** — `Tooltip.tsx:177` backdrop no-op removed (was a dead `backdropFilter: 'blur(0px)'` style with no visual effect).
> - **D3** — `mac-modal-slide-up` keyframe (`Modal.tsx` inline `@keyframes` block, 4 transform refs at lines 328/332/339/343) KEPT as documented exception — Modal entrance animation, canonical animation pattern.
> - **D4** — 15/15 MediLabDemo legacy refs migrated to canonical `mac-entrance-*`/`mac-delay-*`; 4 new `@keyframes` + 4 utility classes (`.mac-entrance-up/left/right` 0.6s ease-out + `.mac-entrance-scale` 0.4s ease-out) + 5 `.mac-delay-100..500` utilities + reduced-motion block update added to tokens.css (+54 LOC). Values byte-identical to legacy `fadeInUp/Left/Right/Scale` (equivalence-by-construction). Legacy keyframes/classes/utilities deleted from animations.css post-migration (0 consumers).
> - **D5** — `landingContent.buildGlassStyle` DEFERRED → PR-16 (Landing redesign).
> - **D6** — `.mac-modal-backdrop` (`tokens.css:495`) + `.clinic-ops-nav-bar` (`macos.css:386`) backdrop KEPT as documented CSS exceptions (sticky-overlay semantics, not component-level glass).
> - **D7** — orphan `components/AnimatedTransition.tsx` (314 LOC, NOT `MacOSEmptyState` — `MacOSEmptyState` was decommissioned earlier in PR #2836 / PR-UI-07a-8b) physically DELETED; 4-proof: (1) 0 importers via grep, (2) 0 dynamic/string imports via `import(`/`require(`/`lazy(` sweep, (3) tsc --noEmit exit 0 post-deletion, (4) canonical `ui/macos/AnimatedTransition` covers production consumers (DoctorPanel:15, QueueView:22, WelcomeView:58 via barrel; InteractivePanel:7 uses local hooks/useAnimation:248).
> - **D8** — `InteractivePanel:38` hover transform removed; calm shadow+border feedback only (no movement).
>
> **AC results (machine-verified on main `ae7236cb6`):**
> - **AC1** — backdrop в components tsx: 27 → **7 ≤10** ✓ (KEEP: Modal, Dialog, CommandPalette, ResponsiveModal, PriceOverrideManager, PWAInstallPrompt, ConnectionStatus).
> - **AC2** — translateY+scale в components: 7 → **0 + D3 documented exception** ✓ (4 transform refs in Modal keyframes — D3).
> - **AC3a** — runtime cursor-effects/sidebar-buttons imports: **0** ✓ (verified: 0 CSS `@import` or TS `import` statements anywhere in `src/`).
> - **AC3b** — stale audit-manifest refs in `frontend/src/utils/frontendAudit.tsx`: **4** (lines 309, 330, 762, 765 — manifest entries listing files as "expected", NOT runtime imports; PR-17 owned follow-up).
> - **AC4** — Sidebar hover = tint+fontWeight only (PR-04 work, already compliant) ✓.
> - **AC5** — prefers-reduced-motion universal block + 8 file-level guards maintained ✓.
>
> **Drift facts recorded in PR #2838 body:**
> 1. `cursor-effects.css` runtime-dead (520 LOC, sole surviving references are 4 audit-manifest entries in `frontendAudit.tsx`, NOT runtime imports) — decommission owned by PR-17.
> 2. Old AC3 (`grep cursor-effects|sidebar-buttons src/` == 0) not a valid runtime test post-PR-08; replaced with AC3a (0 runtime imports) + AC3b (4 stale audit-manifest refs, PR-17 owned).
> 3. transform-keyframes: 0 production consumers (15 all in MediLabDemo demo-only) — corrected from earlier estimate.
> 4. Canonical `mac-*` primitives existed in tokens.css with 0 consumers before PR-08.
> 5. `--mac-card-bg` translucent (rgba 0.88 light / 0.86 dark) vs plan original "solid" — D1 KEEP ruling.
> 6. `.glass` utility dead; glass-scheme removed in PR-02 (vestigial refs in `colorScheme.ts` ROOT_STYLE_PROPERTIES + `HeaderNew.tsx` — follow-up note, not blocking).
> 7. UI-audit track C-4 (commit `c9ea39edd`, 25.08.2026, SEPARATE pre-PR-08 commit, NOT part of #2838) removed `.glass` rule from macos.css pre-PR-08 rebase → PR-08 macos.css deletion became no-op (goal achieved by C-4, not PR-08).
> 8. BS-44 local environmental false-positive — pre-existing (verified on clean main, CI green).
>
> **Ratchet:** PASS — 8 improvements, 0 regressions: `varUsagesNoFallback` 12003→11931 (−72), `cssHexOutsideTokens` 746→738 (−8), `tsxHex` 373→371 (−2), `tsxHexFiles` 64→63 (−1), `duplicateKeyframesNameCount` 10→8 (−2), `unreferencedFileCount` 124→123 (−1), `prefersSchemeRootBlocks` 3→2 (−1, from C-4), `unreferencedFiles` length 124→123.
>
> **Tier-1 + CI on merged SHA `ae7236cb6`:** tsc --noEmit exit 0; vitest 165 files / 1224 tests PASS (20.9s); vite build success (30.3s); lint:check 0 errors / 3090 warnings; check-theme PASS; audit:icon-controls PASS. CI on `ae7236cb6`: 33 check runs = 25 success / 8 skipped (path policy) / 0 failures.
>
> **Scope boundaries respected:** cursor-effects.css, tokens-legacy.ts, ModernTabs rename, MacOSCard/DataCard, landingContent, additional CSS backdrop surfaces (AIChatWindow/ModernDialog/EMRContainerV2/ModernToast/ModernFilters/DoctorTemplatesPanel/AppointmentWizardV2/MacOSDemo) — all owned by their assigned PRs in plan v1.1; not touched in PR-08.
>
> **Original Problem/Solution/AC text below preserved as historical record.** AC3 wording in original AC list below reflects the v1.0/v1.1 contract intent; actual verification post-PR-08 used the AC3a/3b split (see banner above).

**Приоритет:** P1 · **Effort:** 4 SP · **Dependencies:** PR-UI-04 · **Sprint:** 3

**Проблема:** `backdrop-filter` используется 32 раза в CSS + 30 раз в TSX — везде как «стекло». Hover-эффекты с `translateY(-2px) scale(1.02)` создают «прыгающий» UI, неприемлемый для медицинской системы.

**Решение:**

1. ~~**Удалить** `src/styles/cursor-effects.css` (520 LOC)~~ — **ownership перенесён в PR-UI-17** (решение Codex review #2810: 9 interaction-классов ещё потребляются MediLabDemo; PR-08 не совмещает glass/animation canonicalization с legacy-decommission)
2. ~~**Удалить** `src/styles/sidebar-buttons.css` (75 LOC)~~ — ✅ уже удалён в PR-UI-03 (#2810)
3. ~~**Удалить** импорты этих файлов из `MediLabDemo.tsx:13` и `UnifiedSidebar.tsx:8,9`~~ — импорт в UnifiedSidebar ушёл вместе с файлом; импорт `cursor-effects.css` в `MediLabDemo.tsx` остаётся до PR-UI-17

4. **Мигрировать** `backdrop-filter` использования:

   **Glass остается только в:**
   - `macos/Modal.tsx` — modal overlay
   - `macos/Dialog.tsx` — dialog overlay
   - `common/CommandPalette.tsx` — command palette (Cmd+K)
   - `notifications/GlobalNotificationCenter.tsx` — floating notifications

   **Glass удаляется из:**
   - Sidebar (использовать solid `--mac-bg-secondary`)
   - Cards (использовать solid `--mac-card-bg` = `#FFFFFF` в light / `#1C1C1E` в dark)
   - Tables (solid)
   - Header (solid `--mac-bg-primary`)
   - Form inputs (solid)

5. **Мигрировать** hover-эффекты:

   **Было (sidebar-buttons.css):**
   ```css
   .nav-item-hover:hover {
     transform: translateY(-3px) !important;
     box-shadow: 0 8px 20px rgba(0,0,0,0.15) !important;
   }
   ```

   **Стало (в `Sidebar.tsx` inline или в tokens.css):**
   ```css
   .sidebar-item:hover {
     background: var(--mac-accent-bg);  /* tint */
   }
   .sidebar-item.active {
     background: var(--mac-accent-bg);
     color: var(--mac-accent);
     font-weight: 600;
   }
   ```

6. **Обновить** `src/styles/animations.css` (380 LOC):
   - Удалить keyframes с transform/translateY
   - Оставить `fade-in`, `slide-down` (без transform, только opacity + max-height)
   - Все animations обернуть в `@media (prefers-reduced-motion: reduce) { animation: none; }`

7. **Удалить** из `UnifiedSidebar.tsx` (если ещё не удалён в PR-UI-03):
   - `text-shadow: 0 1px 2px rgba(0, 0, 0, 0.35)` (строка 165)
   - `boxShadow: '0 6px 18px rgba(0,0,0,0.18)'` (строка 167)
   - `transform: 'translateY(-2px) scale(1.02)'` (строка 190)
   - `backdropFilter: 'var(--mac-blur-light)'` (строка 191, 203)

**Acceptance criteria:**
- ✅ `grep -rn "backdrop-filter\|backdropFilter" src/components --include="*.tsx" | wc -l` ≤ 10 (только в modal/dialog/command-palette/notifications)
- ✅ `grep -rn "translateY.*scale\|scale.*translateY" src/` — 0 результатов в компонентах
- ✅ `grep -rn "cursor-effects\|sidebar-buttons" src/` — 0 результатов (sidebar-buttons.css уже удалён в PR-UI-03; cursor-effects.css — зона ответственности PR-UI-17)

> **AC3 post-PR-08 verification note (26.08.2026, main `ae7236cb6`):** The original AC3 grep would return **non-zero** (4 stale refs in `frontend/src/utils/frontendAudit.tsx` audit-manifest). Actual verification used the **AC3a/3b split**: AC3a = 0 runtime imports (✓ verified — 0 `@import` or `import` statements anywhere in `src/`); AC3b = 4 stale audit-manifest entries in `frontendAudit.tsx` (PR-17 owned follow-up, NOT runtime concern). The original AC3 wording is preserved above as historical contract intent.
- ✅ Hover на sidebar item = только background tint + font-weight change
- ✅ `prefers-reduced-motion: reduce` отключает все animations
- ✅ Visual regression: UI выглядит «спокойнее», без прыжков

---

### PR-UI-09 — DataTable canonical

> **Статус: 🟡 IN PROGRESS (срез 28.08.2026, main `4228c32d`).** 09a ✅ MERGED (PR #2843 → squash `8143a361`): canonical `DataTable.tsx` 891 LOC, `macos/Table.tsx` → 61 LOC alias (re-export), DataTable-features ×4, tokens.css `mac-table-*` классы, visual e2e spec + 2 snapshot (см. §4.1.6 ledger). 09b ✅ MERGED (PR #2848 → squash `11b423990`): мёртвые реализации DELETED — ResponsiveTable (−468), common/Table (−504), ComponentTest (−281); +1/−1267, 6 файлов; ratchet noFallback −56 (см. §4.1.7 ledger). 09c ✅ COMPLETE (4 инкремента, 28.08.2026; см. §4.1.8 ledger): 09c-1 RefundRequestsTable ✅ (PR #2857 → squash `c8464c81` — alias-decoupling + refunds visual baseline + 1 snapshot); 09c-2 QueueTable ✅ (PR #2860 → squash `e35df1f0` — миграция на canonical DataTable, 4 early-return state сохранены, called-row `:has()`, ratchet −28); 09c-3 alias-decoupling ✅ (PR #2861 → squash `e17d261b` — 10 alias-consumers → прямой import DataTable, zero-delta by construction; живых consumers `macos/Table` = 0); 09c-4 EnhancedAppointmentsTable ✅ (PR #2862 → squash `028ab397` — 2 282 → 2 004 LOC, публичный контракт 6 consumers неизменен, + ModernTabs refetch-flicker fix, ratchet −34). Актуальный LOC таблиц (@ `4228c32d`): DataTable 891, EnhancedAppointmentsTable **2 004**, QueueTable 259, RefundRequestsTable 432, macos/Table 61 alias (0 живых consumers; финальный alias-cleanup — 09d–09e). 09d ✅ MERGED (PR #2870 → squash `7243a108`): физический decommission `macos/Table.tsx` 61-LOC alias + 95-LOC дублирующего теста + barrel table-экспорта; canonical DataTable ре-экспортирован из `ui/` barrel (Codex P2 fix); 6 файлов +19/−167 (см. §4.1.9). 09e-1 ✅ MERGED (PR #2872 → squash `d20cde25`): row virtualization в canonical DataTable (PR-UI-09 AC4) — useVirtualizer + measured geometry + fixed layout + ARIA row-семантика, DT-13..16; zero-delta живых поверхностей (A/B DOM ×4); 0 virtualized consumers на срезе — capability (см. §4.1.9). PR-UI-09 — 🟡 COMPLETE (structural; 4 из 5 AC; AC2 «EAT ≤ 400 LOC» — DEFERRED с полной 6-полей записью в §4.1.9; 8 SP НЕ кредитуются в headline-totals до доставки 09e-2 — AGENTS_UI §13: DEFERRED ≠ completed coverage). Актуальный LOC таблиц (@ `d20cde25`): DataTable 1017 (canonical), EnhancedAppointmentsTable 2 004, QueueTable 259, RefundRequestsTable 432; macos/Table — DELETED (09d). Остаток 09e-2 (LOC-редукция к целям §3.5/§7) — формальная DEFERRED-запись в §4.1.9 (не future-work-заметка): решение пользователя по итогам read-only assessment. Ratchet на срез v1.7: 154/281/11855 (вклад 09d/09e-1 = 0); на main v1.8: 156/282/11883 (Sprint-4 drift, см. §4.1.9). **Ownership-фикс:** `ResponsiveTable` удаляется ЗДЕСЬ (§3.5 ранее ошибочно относила его к PR-17) — выполнено в 09b.

**Приоритет:** P1 · **Effort:** 8 SP · **Dependencies:** PR-UI-06, PR-UI-07 · **Sprint:** 3

**Проблема:** 6 параллельных Table-реализаций (4 496 LOC суммарно). `EnhancedAppointmentsTable` — god-компонент 2 279 LOC.

**Решение:**

1. **Мигрировать** `src/components/ui/macos/Table.tsx` (576 LOC) → canonical `DataTable`:
   - Добавить: sticky header, column sorting, column filtering, pagination, row selection, keyboard navigation, density toggle, empty state, loading skeleton, error state
   - Использовать `@tanstack/react-virtual` (уже в package.json) для virtualization 1000+ rows
   - Целевой размер: ~700 LOC

2. **Мигрировать** `src/components/tables/EnhancedAppointmentsTable.tsx` (2 279 LOC):
   - Сократить до ~400 LOC (только column definitions + actions)
   - Всю logic рендеринга делегировать canonical DataTable
   - Использовать `useMemo` для column config

3. **Удалить** `src/components/common/Table.tsx` (504 LOC) — дубликат
4. **Удалить** `src/components/ResponsiveTable.tsx` (468 LOC) — 0 импортов
5. **Мигрировать** `src/components/cashier/RefundRequestsTable.tsx` (430 LOC → ~150 LOC)
6. **Мигрировать** `src/components/queue/QueueTable.tsx` (239 LOC → ~100 LOC)

7. **Создать** `src/components/ui/DataTable`-features:
   - `TableSkeleton` — skeleton rows во время loading
   - `TableEmpty` — empty state с CTA
   - `TableError` — error state с retry
   - `TablePagination` — sticky bottom pagination

**Acceptance criteria:**
- ✅ `grep -rohE "EnhancedAppointmentsTable|ResponsiveTable|common/Table" src/` — только canonical `DataTable` + thin wrappers (EnhancedAppointmentsTable, RefundRequestsTable, QueueTable) для column config
- ⚠️ **DEFERRED → 09e-2 (формальная 6-полей запись в §4.1.9):** EnhancedAppointmentsTable ≤ 400 LOC — не достигнуто (фактически 2 004 @ `d20cde25`); 09-серия шла zero-delta/contract-preserving путём; редукция = отдельное решение пользователя. Остальные AC выполнены; PR-UI-09 credited 8 SP по deferral-gate.
- ✅ DataTable поддерживает: sticky header, sort, filter, pagination, selection, keyboard nav, density, skeleton, empty, error
- ✅ 1000 rows рендерятся без lag (virtualization)
- ✅ Visual regression на 5 экранах с таблицами

---

## 7. P2: migration & branding (6 PR)

### PR-UI-10 — Branding + Logo + Favicon

> **Статус: ✅ DONE (PR #2867 → squash `865ab5d8` + follow-up #2869 → `66c7ceff`, 28.08.2026; см. §4.1.9).** Верифицировано на main: `public/brand/{logo.svg,logo-mark.svg}` созданы; `brand.ts` name/shortName = 'Clinic OS'; упоминаний «MediClinic Pro» в src — **0** (fresh grep 29.08; план исходил из 36 → 20 → 0).

**Приоритет:** P2 · **Effort:** 3 SP · **Dependencies:** — · **Sprint:** 4

**Проблема:** `src/config/brand.ts:36,38` указывает на `/brand/logo.svg` и `/brand/logo-mark.svg`, но каталог `public/brand/` не существует. 36 упоминаний "MediClinic Pro" + "Clinic OS" в `landingContent.ts` — двойное имя продукта путает.

**Решение:**

1. **Унифицировать** в `src/config/brand.ts`:
```ts
export const BRAND = {
  name: 'Clinic OS',
  shortName: 'Clinic OS',
  tagline: 'EMR, очередь и платежи в одном контуре',
  legalName: 'Система управления клиникой',
  category: 'Clinic management system',
  logo: '/brand/logo.svg',
  logoMark: '/brand/logo-mark.svg',
  supportEmail: 'support@clinic-os.example',
  version: '2.0.0',
};
```

2. **Создать** `public/brand/logo.svg` — SVG-логотип Clinic OS (минималистичный, медицинский teal + белый)

3. **Создать** `public/brand/logo-mark.svg` — монограмма 32×32 для favicon

4. **Заменить** `public/favicon.ico` — на logo-mark

5. **Мигрировать** `src/pages/landingContent.ts` — заменить все 36 упоминаний "MediClinic Pro" на "Clinic OS"

6. **Обновить** `public/manifest.json` — name/short_name/icons

7. **Обновить** `index.html` — title, meta tags, favicon links

**Acceptance criteria:**
- ✅ `grep -r "MediClinic Pro" src/` — 0 результатов
- ✅ `public/brand/logo.svg` существует и валидный SVG
- ✅ Favicon отображается в браузере
- ✅ Все 5 локалей в `landingContent.ts` используют "Clinic OS"

---

### PR-UI-11 — Dashboard redesign (data-first)

> **Статус: 🟡 IN PROGRESS (срез 29.08.2026 v1.9, main `64f73d40`; см. §4.1.9–4.1.10).** 12 инкрементов MERGED: 11-1 ✅ (PR #2871 → `1378d6ef`) — AdminDashboard data-first + canonical `DataCard.tsx`, 10 файлов +1359/−151; 11-2..11-12 ✅ (PR #2873 → `32edbc20`; #2876 → `b5dc46d7`; #2878 → `0eb96756`; #2880 → `7a511d7d`; #2882 → `15e484bc`; #2884 → `68f51d9d`; #2886 → `aef6b344`; #2888 → `d5bcf003`; #2889 → `1dac9278`; #2892 → `0c9b621c` cardio; #2894 → `61468afe` derma) — MacOSCard-потребители мигрированы на canonical Card. Остаток: `MacOSCard` жив в **12 файлах** (fresh grep 29.08 @ `64f73d40`; было 61 на срезе v1.8) — миграция consumers продолжается соседним workstream'ом.
>
> **⚠️ Legacy debt от PR-UI-06 (PARTIAL):** canonical card strategy разрешается ЗДЕСЬ — миграция живых `MacOSCard` consumers (329 JSX) на canonical `Card` и введение `DataCard` (см. §3.4). PR-UI-06 не классифицируется как completed до выполнения этого пункта. Не переносить этот хвост в PR-17: это живые consumers, а не доказанно dead code.

**Приоритет:** P2 · **Effort:** 5 SP · **Dependencies:** PR-UI-09 (+ закрытие legacy-хвоста PR-UI-06: миграция `MacOSCard` → canonical `Card`, создание `DataCard`) · **Sprint:** 4

**Проблема:** Текущий `AdminDashboard.tsx` (488 LOC) использует 6 glass-карточек с градиентами + большими иконками. Это landing-page стиль, не data-first.

**Решение:**

1. **Обновить** `src/components/admin/AdminDashboard.tsx` — data-first layout:
   - Header: "Доброе утро, Dr. ..." + дата
   - Today's schedule (timeline: 08:30 Patient A Cardiology / 09:00 Patient B Follow-up / ...)
   - Queue summary (3 stat cards: Waiting / In consultation / Done)
   - Revenue today / Patients today / Appointments today (3 StatCards)
   - Recent activity feed

2. **Удалить** glass cards с градиентами

3. **Использовать** canonical `StatCard` + `DataCard`

4. **Добавить** skeleton loading для async data

**Acceptance criteria:**
- ✅ Dashboard содержит: schedule timeline + queue summary + 3 stat cards + activity feed
- ✅ Нет glass cards с градиентами
- ✅ Loading state = skeleton (не spinner)
- ✅ Visual regression

---

### PR-UI-12 — EMR + Queue + Table UX

> **Статус: ✅ DONE (4 инкремента, 29.08.2026; см. §4.1.10).** 12-1 ✅ (PR #2885 → `4199b9c2`) — DataTable UX feature layer: sticky filters (measured offset — 12-1 исправил конфликт «обе строки sticky top:0»), column visibility + toolbar, density toggle, roving keyboard nav; 28 новых DT-тестов; 14 Codex-находок (13 fixed, 1 DEFERRED с 6-полей записью). 12-2 ✅ (PR #2890 → `f4d577d7`) — QueueTable roving keyboard nav; §18 divergence задокументирована: «Enter для вызова пациента» плана vs QueueManager.contract «call-next = backend-owned command» — repo-инвариант выиграл. 12-3 ✅ (PR #2891 → `26347af3`) — EMR section skeleton loading (строго `isLoading && !data` — первый load only, autosave/refresh не флэшают скелет над вводом врача). 12-4 ✅ (PR #2893 → `64f73d40`) — sticky table headers на предусмотренных поверхностях + visual regression AC на 5 экранах (EMR/Queue/Appointments/Patients/Lab); ПОДТВЕРЖДЁННАЯ архитектурная находка: page-level sticky невозможен под `.app-shell-grid` (inline overflowY auto + overflowX hidden = scroll-container между th и документом) → canonical-решение = per-table bounded viewport (`stickyHeader + maxHeight` в kit); at-rest zero-delta доказан существующими baseline'ами. Все 4 AC-пункта плана выполнены; ratchet-вклад серии = 0.

**Приоритет:** P2 · **Effort:** 8 SP · **Dependencies:** PR-UI-07, PR-UI-09 · **Sprint:** 4

**Решение:**

1. **EMR sections** — каждый раздел (Anamnesis, Complaints, Examination, Diagnosis, Treatment, Lab results) — skeleton loading
2. **QueueTable** — keyboard nav (ArrowUp/ArrowDown для перемещения, Enter для вызова пациента)
3. **DataTable** — sticky filters, column visibility, density toggle (compact/comfortable)
4. **Все** таблицы — sticky header при скролле

**Acceptance criteria:**
- ✅ EMR sections показывают skeleton во время loading
- ✅ QueueTable поддерживает keyboard nav
- ✅ DataTable: sticky filters + column visibility + density toggle
- ✅ Visual regression на 5 экранах (EMR, Queue, Appointments, Patients, Lab)

---

### PR-UI-13 — Migration: RegistrarPanel

> **Статус: ⬜ NOT STARTED (срез 25.08.2026).** RegistrarPanel — фактически 2 240 LOC (соответствует плану).

**Приоритет:** P2 · **Effort:** 8 SP · **Dependencies:** PR-UI-04, PR-UI-09 · **Sprint:** 5

**Проблема:** `RegistrarPanel.tsx` — 2 240 LOC, 25 useState, god-компонент.

**Решение:**

1. **Декомпозировать** до ~500 LOC:
   - Вынести state в `useReducer` (top-level state machine)
   - Вынести wizard/dialog logic в hooks: `useRegistrarWizard`, `useRegistrarDialogs`
   - Использовать canonical DataTable + AppEmpty

2. **Мигрировать** на новый AppShell (из PR-UI-04)

3. **Мигрировать** на canonical Button/Card/Table primitives

4. **Добавить** локальный `ErrorBoundary` вокруг wizard

**Acceptance criteria:**
- ✅ RegistrarPanel ≤ 500 LOC
- ✅ useState ≤ 5 (остальные в useReducer)
- ✅ Локальный ErrorBoundary
- ✅ Все тесты зелёные
- ✅ Visual regression

---

### PR-UI-14 — Migration: CashierPanel

> **Статус: ⬜ NOT STARTED (срез 25.08.2026).** CashierPanel — фактически 2 125 LOC (соответствует плану).

**Приоритет:** P2 · **Effort:** 6 SP · **Dependencies:** PR-UI-04, PR-UI-09 · **Sprint:** 5

**Проблема:** `CashierPanel.tsx` — 2 125 LOC, 38 useState.

**Решение:**

1. **Декомпозировать** до ~500 LOC + useReducer
2. **Мигрировать** `RefundRequestsTable` на canonical DataTable
3. **Добавить** локальный ErrorBoundary

**Acceptance criteria:**
- ✅ CashierPanel ≤ 500 LOC
- ✅ useState ≤ 5
- ✅ RefundRequestsTable ≤ 150 LOC
- ✅ Локальный ErrorBoundary

---

### PR-UI-15 — Migration: Doctor + Dentist

> **Статус: ⬜ NOT STARTED (срез 25.08.2026).** DoctorPanel — 1 330 LOC; DentistPanelUnified — фактически **2 148 LOC** (план указывал 2 419; drift −271).

**Приоритет:** P2 · **Effort:** 10 SP · **Dependencies:** PR-UI-12, PR-UI-13 · **Sprint:** 5

**Проблема:** `DoctorPanel.tsx` — 1 330 LOC, `DentistPanelUnified.tsx` — 2 419 LOC.

**Решение:**

1. **Декомпозировать** DoctorPanel до ~500 LOC
2. **Декомпозировать** DentistPanelUnified до ~600 LOC
3. **Специальности** — accent color только в header (cardio=red, derma=violet, dentist=blue), не во всём UI
4. **Единый** EMR для всех specialities (различаются только templates)
5. **Локальные** ErrorBoundary

**Acceptance criteria:**
- ✅ DoctorPanel ≤ 500 LOC
- ✅ DentistPanelUnified ≤ 600 LOC
- ✅ Specialty color — только в header badge, не во всём UI
- ✅ Единый EMR

---

### PR-UI-19 — Navigation i18n (C-6 remediation)

> **Статус: ✅ DONE (PR #2879 → squash `faace538`, 29.08.2026; см. §4.1.10).** Верифицировано на merged tree: 0 кириллических `label:` в routeRegistry (grep-гвард в тесте); 51 nav.*-ключ × 5 локалей (ru byte-identical, uz-Cyrl реальные переводы, kk medical-draft wording «Қаралған»/«Жазылымдар» корректен); labelKey/sectionKey через t() в Sidebar + CommandPalette; реактивное переключение языка без reload (тест-покрыто). Audit finding C-6 закрыт.

**Приоритет:** P2 · **Effort:** 3 SP · **Dependencies:** — · **Sprint:** 5 (исполним параллельно с PR-UI-13..15; не зависит от них)

**Finding (UI_AUDIT_PLAN.md, C-6):** sidebar-навигация всегда на русском — 61 label без i18n в `routeRegistry.ts` (аудит 18.08.2026).

**Current evidence (fresh, main `ad2f44ac`, 29.08.2026):** **67** hardcoded русских `label:` в `frontend/src/routing/routeRegistry.ts` (`'Обзор'`, `'Очередь'`, `'Записи'` …; аудит фиксировал 61 — рост за счёт новых пунктов навигации); **0** использований i18n в routeRegistry. **Affected files:** `frontend/src/routing/routeRegistry.ts` (SIDEBAR_PRESETS, все label-поля), `frontend/src/routing/routeSelectors.ts` (**главный consumer label**: реконструкция SidebarItem через `label: navMeta?.label || navRoute.title` в admin и clinical ветках, строки ~443–467; тип `SidebarItem` не имеет labelKey — требует расширения), `frontend/src/i18n/locales/{ru,en,kk,uz-Cyrl,uz-Latn}.ts` (5 локалей), `components/ui/macos/Sidebar.tsx` (финальный рендер). Примечание (Codex #2875): `HeaderNew` registry-labels не потребляет — исключён из scope.

**Решение:**

1. Каждый `label: '…'` → `labelKey: 'nav.<route-id>'` (конвенция — по i18n-адаптеру проекта)
2. Добавить ключи `nav.*` во все **5 локалей** (ru / en / kk / uz-Cyrl / uz-Latn; существующие переводы терминологии — источник)
3. `routeSelectors.ts` **строго пробрасывает `labelKey`** в `SidebarItem` — НЕ резолвит `t()` в селекторе: `App.tsx:170-180` (AppShell) вычисляет `getRouteChromeState()` без i18n-подписки, уже-переведённые строки не обновятся при смене языка до неродственного re-render/navigation; Sidebar — единственный подписчик `useTranslation()` — резолвит `t(labelKey)` в рендере; **fallback**: ключ отсутствует → текущий русский текст (навигация не ломается при пропущенном ключе)

**Acceptance criteria:**

- ✅ 0 hardcoded кириллических label в `routeRegistry.ts` (grep-гвард `label:\s*'[^']*[А-Яа-яЁё]` = 0)
- ✅ `nav.*`-ключи присутствуют во всех 5 локалях; i18n contract-тест расширен
- ✅ Sidebar отображает локализованные labels минимум в ru + en (browser-проверка); переключение языка меняет навигацию без перезагрузки И без навигационного действия (реактивно — резолюция в Sidebar через useTranslation, не в селекторе; иначе — см. App.tsx:170-180 замечание в решении)
- ✅ Tier-1 + e2e green; ratchet не хуже текущего среза

**Risk:** LOW — рендер-слой навигации, не клиника/бизнес-логика; риск пропущенных переводов закрыт fallback-стратегией; объём ~67×5 строк переводов требует аккуратности (kk/uz — сверять с существующей терминологией в локалях).

**Owner/workstream:** на срез v1.8 не назначен; кандидат — ближайший свободный агент-инкремент Sprint 5 (исполнитель PR-UI-19 = кто первым взял; координация через open-PR check).

## 8. P3: landing & polish (3 PR)

### PR-UI-16 — Landing redesign

> **Статус: ⬜ NOT STARTED (срез 25.08.2026).**

**Приоритет:** P3 · **Effort:** 8 SP · **Dependencies:** PR-UI-10, PR-UI-11 · **Sprint:** 6

**Решение:**

1. **Hero** с реальным screenshot продукта (не абстрактный dashboard из красивых карточек)
2. **Workflow diagram** как центральный элемент: Patient → Registrar → Queue → Doctor → EMR → Payment → Report
3. **Screenshots** вместо иконок в FEATURE_VISUALS / MODULE_VISUALS
4. **Убрать** glass cards с градиентами
5. **Структура:** Hero → Social proof → Features → Workflow → Modules → Screenshots → Integrations → Security → Pricing → FAQ → CTA

**Acceptance criteria:**
- ✅ Hero содержит реальный screenshot интерфейса
- ✅ Workflow diagram показывает 7 шагов
- ✅ Нет glass cards с градиентами
- ✅ Visual regression

---

### PR-UI-17 — Cleanup: dead code removal

> **Статус: ⬜ NOT STARTED (срез 26.08.2026, main `ae7236cb6`).** **Ownership-сводка:** этот PR — владелец удаления `cursor-effects.css` (перенос из PR-08; PR-08 verification в #2838 confirmed runtime-dead: 0 runtime imports — AC3a ✓; 4 stale audit-manifest refs in `frontendAudit.tsx` — AC3b, этого PR owned cleanup), `tokens-legacy.ts` (перенос из PR-02) и rename `ModernTabs → Tabs` (перенос из PR-04). `sidebar-buttons.css` + `unified-sidebar.css` + `UnifiedLayout` уже удалены в PR-UI-03 — в списке ниже отмечены. **Additional follow-ups discovered during PR-08 (26.08.2026, не blocking):** (a) `colorScheme.ts` ROOT_STYLE_PROPERTIES vestigial refs (PR-02 glass-scheme removal residual); (b) `HeaderNew.tsx` vestigial glass refs; (c) additional CSS backdrop surfaces (AIChatWindow/ModernDialog/EMRContainerV2/ModernToast/ModernFilters/DoctorTemplatesPanel/AppointmentWizardV2/MacOSDemo) — minor cleanup candidates, candidates for этого PR или отдельный cleanup track. **M-8 ownership (v1.8, Codex #2875 round 2):** dead-duplicate decommission + consolidation inventory — см. пункт 12 и AC ниже.

**Приоритет:** P3 · **Effort:** 5 SP (3 исходных + 2 за M-8 ownership, v1.8) · **Dependencies:** PR-UI-15 · **Sprint:** 6

**Решение:**

1. **Удалить** `src/components/medical/` (4 файла, 1 097 LOC)
2. **Удалить** `src/components/forms/Modern*` (4 файла, 705 LOC)
3. **Удалить** в `src/components/layout/`: ~~`UnifiedSidebar.tsx`, `UnifiedLayout.tsx`~~ (✅ уже удалены в PR-UI-03 #2810), ~~`ModernCard.tsx`~~ (✅ уже удалён в PR-UI-06 #2820), `ModernContainer.tsx`, `ModernFlex.tsx`, `ModernGrid.tsx`, `Nav.tsx`
4. **Удалить** `src/styles/cursor-effects.css` (520 LOC; владелец — этот PR, перенос из PR-08 по решению Codex review #2810). ~~`sidebar-buttons.css`, `unified-sidebar.css`~~ — ✅ уже удалены в PR-UI-03 (#2810)
5. **Удалить** `src/components/Icon.tsx` + `src/assets/iconsMap.ts`
6. **Удалить** `src/components/common/Table.tsx`, `src/components/common/Modal.tsx` (~~`src/components/ResponsiveTable.tsx`~~ — ownership перенесён в PR-UI-09, см. §3.5)
7. **Удалить** `src/components/ui/macos/Icon.tsx` (если все потребители мигрированы на lucide-react)
8. **Добавить** stylelint-правило `declaration-property-value-allowed-list` для spacing
9. **Добавить** ESLint-правило для forbidden imports
10. **Удалить** `src/theme/tokens-legacy.ts` — после устранения единственного живого импортёра (`ThemeContext.tsx`); ownership перенесён из PR-UI-02 (см. §3.1)
11. **Переименовать** `src/components/navigation/ModernTabs.tsx` → `Tabs.tsx` — mechanical rename, отложен из PR-UI-04 (33 потребителя)
12. **M-8 dead-duplicate decommission + consolidation inventory (ownership присвоен v1.8; audit M-8):**
    - Удалить мёртвый `src/components/telegram/TelegramManager` (741 LOC — дубликат root-живого `TelegramManager` 2 496 LOC) **вместе с его единственным импортёром `src/pages/TelegramPage.tsx`** (мёртвая страница: живых импортёров нет — упоминания только как i18n-ключи в 5 локалях, вычистить ключи; иначе tsconfig include `src/**/*.tsx` даёт unresolved import и type-check FAIL — Codex #2875 round 3). Перед удалением grep-проверка 0 живых импортёров по прецеденту cursor-effects #2838
    - Составить consolidation-inventory по: 2FA ×6 файлов, `PWAInstallPrompt` ×3, role-гварды ×4 — per-entity решение (мёртвые дубликаты удаляются здесь; живые консолидации — отдельный инкремент с явным решением, зафиксированным в плане)
    - Affected paths: `frontend/src/components/telegram/`, `frontend/src/pages/TelegramPage.tsx`, 2FA-файлы (список M-8 аудита), `PWAInstallPrompt*`, role-guard helpers
13. **L-5 ownership (v1.8, Codex #2875 round 3):** удалить мёртвую пару `src/PublicApp.tsx` + `src/pages/Login.tsx` (PublicApp не импортируется нигде в src — grep 29.08; Login импортируется только PublicApp'ом); вычистить `legacyRedirectFrom: ['/old-login']` из `routeRegistry.ts` (~строка 225) и связанные i18n-ключи; после удаления — grep-проверка 0 ссылок

**Acceptance criteria:**
- ✅ Все перечисленные файлы удалены
- ✅ `npm run type-check` без ошибок
- ✅ `npm run lint:check` без ошибок
- ✅ Stylelint отклоняет нестандартные spacing values
- ✅ ESLint отклоняет forbidden imports
- ✅ Bundle size уменьшился на ≥ 50 KB gzip
- ✅ (M-8, v1.8) Мёртвый `components/telegram/TelegramManager` удалён вместе с единственным импортёром `pages/TelegramPage.tsx` (0 unresolved imports, type-check PASS); consolidation-inventory по 2FA/PWA/role-гвардам зафиксирован в плане; живые дубликаты не тронуты без отдельного решения
- ✅ (L-5, v1.8) `PublicApp.tsx` + `pages/Login.tsx` удалены; `legacyRedirectFrom: ['/old-login']` вычищен из routeRegistry; 0 ссылок после удаления

---

### PR-UI-18 — Visual regression suite

> **Статус: ⬜ NOT STARTED (срез 25.08.2026).**

**Приоритет:** P3 · **Effort:** 5 SP · **Dependencies:** all · **Sprint:** 6

**Решение:**

1. **Playwright snapshots** для 12 ключевых экранов в light/dark:
   - Landing, Login, /admin, /registrar, /doctor, /cashier, /lab, /doctor/cardiology, /doctor/dermatology, /doctor/dentistry, /patient, /display-board

2. **Storybook stories** для всех canonical primitives: Button, Card, StatCard, DataCard, DataTable, Modal, AppState, Input, Select, Textarea

3. **Chromatic / Percy** deploy gate (визуальный diff в PR)

4. **a11y axe** интеграция в Playwright

**Acceptance criteria:**
- ✅ 12 экранов × 2 темы = 24 snapshots в CI
- ✅ Storybook stories для всех primitives
- ✅ Visual diff gate в PR (не даёт мерджить при regressions)

---

## 9. Regression strategy

После каждого PR запускать:

```bash
# Unit tests (314 contract + unit)
npm run test:run

# E2E + visual regression + a11y + load
npm run test:e2e:run

# TypeScript strict
npm run type-check

# ESLint + jsx-a11y
npm run lint:check

# Theme compliance
npm run check-theme

# A11y icon controls audit
npm run audit:icon-controls

# Bundle analysis (size regression)
npm run build:analyze

# Mutation testing (nightly, not per-PR)
# npm run test:mutation (если настроен mutmut + Stryker)
```

**Правило:** PR не мерджится, если любой из шагов красный. Исключений нет.

---

## 10. Risk matrix

| Риск | Вероятность | Impact | Mitigation |
|---|---|---|---|
| Пользователи registrar/cashier теряются при смене header-tabs → sidebar | Высокая | Средний | Онбординг-баннер «Изменилась навигация» в течение 2 недель после деплоя |
| Удаление MacOSThemeProvider ломает кастомные accent colors у пользователей | Низкая | Низкий | localStorage migration script: удалить ключ `ui.accent` |
| Удаление vibrant/glass/gradient тем недовольны админы | Низкая | Низкий | Все 3 темы остаются в `/internal-demo/*` роутах (не в production UI) |
| God-компоненты (RegistrarPanel, CashierPanel) ломаются при декомпозиции | Высокая | Высокий | Полный regression-gate после каждого PR; мигрировать по одной панели за спринт |
| Visual regression ловит существующие «баги» как новые | Средняя | Средний | Обновить baseline-снапшоты перед началом миграции; помечать intentional changes |
| Bundle size растёт из-за дублирующих компонентов во время миграции | Средняя | Низкий | PR-UI-17 (cleanup) в конце; промежуточные PR могут временно увеличивать bundle |
| Удаление Icon.tsx ломает потребителей, которых не нашли | Низкая | Средний | Полный grep по `assets/iconsMap` + `from '../Icon'` + `from '@/components/Icon'` перед удалением |
| `tsc --noEmit` падает на 30+ файлах после ужесточения Button variant | Высокая | Низкий | Это ожидаемо — исправить в том же PR; не растягивать на несколько PR |

---

## Приложение A: Метрики успеха

После завершения всех 19 PR:

| Метрика | Текущее значение | Целевое значение |
|---|---|---|
| ThemeProvider'ов | 2 (ThemeContext + MacOSThemeProvider) | 1 (theme: 'light' \| 'dark' \| 'auto' + resolvedTheme) |
| Color schemes | 6 (light/dark/auto + vibrant/glass/gradient) | 3 (light/dark/auto) |
| Card-типов | 8 | 3 (Card/StatCard/DataCard) |
| Table-реализаций | 6 | 1 canonical DataTable + thin wrappers |
| Icon-систем | 2 (lucide-react + Icon.tsx SF Symbols) | 1 (lucide-react) |
| Навигационных моделей | 3 (sidebar/header-tabs/ModernTabs) | 1 (sidebar RBAC-driven) |
| Inline-style блоков | 2 256 | ≤ 200 (только в Pages, не в primitives) |
| backdrop-filter в components | 30 | ≤ 10 (только modal/dialog/command-palette/notifications) |
| `translateY/scale` hover effects | 17 | 0 |
| God-компоненты (> 1000 LOC) | 7 | 0 (макс ~600 LOC) |
| Bundle size (gzip) | ~? KB | -50 KB после cleanup |
| Пользовательских color schemes | 6 | 0 (только canonical light/dark/auto) |
| Мёртвых CSS-файлов | 3 (cursor-effects, sidebar-buttons, unified-sidebar) | 0 |
| Мёртвых component-каталогов | 2 (medical/, forms/Modern*) | 0 |

**Срез 29.08.2026 (main `ad2f44ac`, v1.8):** Table-реализаций — **4** (1 canonical DataTable 1017 LOC + 3 thin wrappers: EAT 2 004 / QueueTable 259 / RRT 432; macos/Table alias удалён 09d #2870; common/Table и ResponsiveTable удалены 09b #2848); AC4 virtualization capability готова (09e-1 #2872). Card — canonical Card/StatCard/DataCard существуют; MacOSCard жив в 61 файле → PR-UI-11 IN PROGRESS. ThemeProvider — 1 (PR-UI-01 #2812); color schemes — 3 (PR-UI-02 #2814). Мёртвые CSS: cursor-effects.css runtime-dead (0 импортов, #2838), физически в репо → PR-UI-17. Ratchet: names/usages/noFallback **156/282/11883** vs baseline 163/330/12003 — ниже baseline на всём горизонте наблюдения, gate PASS на каждом merge. Политика гейта — baseline-bound (не merge-to-merge): исторические merge-to-merge росты — только 2 атрибутированных drift-события вне UI-audit workstream: +4 names/usages #2847 (§4.1.6) и +2/+1/+28 #2871 (§4.1.9).

---

## Приложение B: Связанные документы

- `AGENTS_UI.md` — жёсткий контракт для AI-агента (13 правил do/don't)
- `frontend/DESIGN_SYSTEM.md` — текущая документация дизайн-системы (обновить в PR-UI-02)
- `frontend/DESIGN_SYSTEM_ENFORCEMENT.md` — enforcement rules (обновить)
- `frontend/ADR-0013..0018` — архитектурные решения (не трогать, но соблюдать)
- `frontend/src/routing/routeRegistry.ts` — реестр маршрутов (расширить в PR-UI-04)
- `docs/runbooks/STAGING_VALIDATION.md` — pre-deploy checks
- `frontend/e2e/AUTHENTICATED_UI_QA.md` — QA checklist для аутентифицированных экранов

---

## Приложение C: Audit → Plan completeness matrix (v1.8, срез 29.08.2026, main `ad2f44ac`)

> Машинно-проверяемая матрица полноты: ни одна finding аудита (UI_AUDIT_PLAN.md §4: C-1..C-6, H-1..H-12, M-1..M-12, L-1..L-6) не должна теряться между audit → plan → implementation. Статусы: ✅ DONE · 🟡 PARTIAL/ACTIVE · ⬜ PLANNED · 🔁 DECISION-REVERSED · 📌 DIVERGENT-RULING (план осознанно разошёлся с аудитом — кандидат явного решения). Evidence — PR#/SHA, live-grep срез 29.08, или раздел плана.

| Finding | Remediation item | PR / механизм | Статус | Evidence |
|---|---|---|---|---|
| **C-1** Toast/Modal на `--color-*` из неподключённого admin-styles.css | Hotfix Phase 1.1: статусные цвета на `--mac-*` | hotfix + PR-UI-02 era | ✅ DONE | live: `Toast.tsx` 20 × `var(--mac-*)`, `common/Modal.tsx` 19 ×; мёртвый `admin-styles.css` (379 LOC, 0 импортов) → физическое удаление PR-UI-17 |
| **C-2** Модалка «Осмотр» DentistPanelUnified на Tailwind-классах | PR-UI-15: декомпозиция + kit | PR-UI-15 (Sprint 5) | ⬜ PLANNED | §7 PR-UI-15; DentistPanelUnified 2 148 LOC (drift −271 к плану) |
| **C-3** 151 undefined-токен / 369 битых var() | Phase 2A/2B/2C + ratchet-политика | `9b1ef5d` (2A), `26410a025` (2B-A), `e16f3b0c` (2C) | ✅ DONE (топ-семейства) + 🟡 ACTIVE | VERIFIED-ledgers §4.1.3–4.1.5; names 163→156, gate PASS на каждом merge |
| **C-4** `@media(prefers-color-scheme:dark):root` в macos.css навязывает dark | Удаление блока | PR-UI-02 #2814 | ✅ DONE | §3 matrix row: MIGRATE ✅ #2814 |
| **C-5** a11y-слой (accessibility.css) не подключён | Критичное канонизировано; глобальный слой — решение | hotfix + решение в `tokens.css:926-933` | 🟡 PARTIAL-BY-DECISION | sr-only canonical (C-5 fix comment live); остальной слой осознанно не подключён — риск visual-regression + overlap, задокументирован; adoption → отдельное решение/PR-UI-17-track |
| **C-6** 61 (→67) nav-label без i18n | **NEW PR-UI-19 (§7)** — введён в v1.8 | PR-UI-19 (Sprint 5) | ⬜ TRACKED (ранее ORPHANED) | fresh grep 29.08: 67 кириллических `label:` в routeRegistry.ts, 0 i18n; 5 локалей готовы |
| **H-1** 6 систем токенов | PR-UI-02: tokens.css SSOT; alias-роспуск — фаза 7.2 | PR-UI-02 #2814; хвост PR-UI-17 | ✅ DONE + ⬜ хвост | §3: macos-tokens MIGRATE ✅ #2814; alias-слой жив до фазы 7 |
| **H-2** Инвертированный каскад (патчи раньше базы) | §3 ruling KEEP для dark-fix/global-fixes; роспуск патчей — фаза 7.1 | PR-UI-17-track | 📌 DIVERGENT-RULING | live main.tsx: theme → dark-fix → global-fixes → tokens → macos → admin; §3 rows 134-135 KEEP; распускание при росте adoption (фаза 7) |
| **H-3** emr-tokens.css dark-only палитра в `:root` | §3 ruling KEEP; аудит-фикс «выразить через --mac-*» не принят | Sprint 5 EMR-секции (PR-UI-15/12) | 📌 DIVERGENT-RULING | live: `:root { --surface-app:#0f0f23; … }` в emr-tokens.css (grep 29.08); §3 row 240 KEEP; кандидат явного решения |
| **H-4** JS-мост тем (ThemeContext пишет CSS-переменные) | PR-UI-01: единый провайдер; legacy JS-токены → DELETE | PR-UI-01 #2812; tokens-legacy → PR-UI-17 | 🟡 PARTIAL | macosTheme.tsx DELETED ✅ #2812; live: `theme/tokens-legacy.ts` + `tokens.ts` ещё в репо → PR-UI-17 |
| **H-5** DoctorPanel: sidebar + 6 inline-табов JS-hover | PR-UI-15 | PR-UI-15 (Sprint 5) | ⬜ PLANNED | §7 PR-UI-15 |
| **H-6** 22 модалки вне кита; Modal и Dialog одновременно | Решение REVERSED: канон — kit Modal.tsx | канон live; consumers → Sprint 5 | 🔁 DECISION-REVERSED + 🟡 | целевая архитектура §2; `common/Modal.tsx` 19 × `var(--mac-*)`; доменные *Modal*.tsx мигрируют в PR-UI-13..15 |
| **H-7** 2 тост-системы (сломанная кастомная + toastify) | notify.ts канон; ToastProvider decommission | services/notify.ts live; ToastProvider → PR-UI-17-track | 🟡 PARTIAL | live: `services/notify.ts` существует; ToastProvider ещё подключён (AppProviders/Toast.tsx) |
| **H-8** 8-11 utility-диалектов (~5 700 строк page-CSS) | Sprint 5 волны 5.3 (admin) и домены | PR-UI-13..15 (Sprint 5) | ⬜ PLANNED | §7; admin.css 12 657 LOC жив |
| **H-9** ~7 000+ строк мёртвого кода | PR-UI-17: decommission | PR-UI-17 | ⬜ PLANNED (runtime-dead proof есть) | cursor-effects.css 0 импортов (#2838); medical/, forms/Modern* 0 импортёров; MediLabDemo demo-only |
| **H-10** Dark-тема непокрыта (182 isDark-ветвления) | Токен-миграция доменов | Sprint 5 (ongoing) | 🟡 ACTIVE | ratchet noFallback 12003 (baseline) → 11883 ниже baseline; росты только в 2 атрибутированных drift-событиях (#2847, #2871) |
| **H-11** Tailwind-осколки в живых страницах | QueueJoin (5.6), DentistPanelUnified (C-2) | Sprint 5 / PR-UI-15 | ⬜ PLANNED | §7 PR-UI-15 + §6 волны 5.6 |
| **H-12** internal-demo-роуты (~3 000+ строк) в прод-бандле | MediLabDemo MIGRATE (§3 row 152) | флаг VITE_ENABLE_INTERNAL_DEMO live; полная декомиссия → PR-UI-17 | 🟡 PARTIAL | live: гейт флага существует; решение «удалить полностью» — PR-UI-17 |
| **M-1** ≥6 реализаций табов / 4 списка пациентов / 5+ empty-state / 6 лоадеров | PR-UI-05..09 серия | Button ✅ (PR-UI-05 + P1a); AppState ✅ (PR-UI-07 + 07a #2824–#2836); Tables ✅ (PR-UI-09 COMPLETE); Tabs 🟡 | 🟡 PARTIAL | ModernTabs сохранён как content-tabs (33 потребителя), rename → PR-UI-17; Card-хвост → PR-UI-11 |
| **M-2** ~2 600 inline-стилей | Ratchet-политика | ui-baseline `--check` gate | ✅ ACTIVE | noFallback 12003 (baseline) → 11883; все merges ниже baseline, gate PASS; merge-to-merge росты — только 2 атрибутированных drift-события (#2847 §4.1.6, #2871 §4.1.9), оба вне UI-audit workstream; baseline не тронут |
| **M-3** ~692 hex TSX + ~1 127 hex CSS | CI-guard + ratchet | no-hardcoded-colors / Regression Audit Gate | ✅ ACTIVE | names/usages в gate (156/282); hex-регекс false-positives документированы (v1.7 §4.1.8) |
| **M-4** Коллизии keyframes (spin×17, pulse×9…) | PR-UI-08 D4: mac-entrance канон | PR-UI-08 #2838 | 🟡 PARTIAL | entrance-семейство канонизировано (byte-identical); остальные дубли → Sprint 5/PR-UI-17 |
| **M-5** 19 брейкпоинтов; 2 хука медиазапросов | Шкала в tokens.css (#2814) + вычистка доменов | Sprint 5; PR-UI-18 | 🟡 PARTIAL | canonical-шкала зафиксирована; page-CSS остатки → волны 5.x |
| **M-6** i18n-конвенции ключей разнородны | Схема `<domain>.<section>.<key>` в новых ключах; nav.* — PR-UI-19 | PR-UI-19 + Sprint 5 | 🟡 PARTIAL | i18n contract-тесты live (Admin/Dental/Payment); nav.*-блок — в PR-UI-19 |
| **M-7** 73 native select / title= вместо Tooltip / эмодзи-иконки | Kit-компоненты при доменной миграции | Sprint 5 | ⬜ PLANNED | §6 волны 5.x |
| **M-8** 4 role-гварда / 6 файлов 2FA / 3 PWA / 2 TelegramManager | Консолидация по одному на сущность | PR-UI-17 (item 12 + AC, v1.8) | ⬜ PLANNED | §7 PR-UI-17: telegram-дубликат 741 LOC DELETE + consolidation-inventory; effort +2 SP |
| **M-9** 24 font-family / 22 font-size / 30 radius | Шкалы `--mac-*` в tokens.css | PR-UI-02 #2814 + Sprint 5 остатки | 🟡 PARTIAL | canonical-шкалы live; page-CSS остатки → волны 5.x |
| **M-10** Settings на второй токен-системе + вкладки вне URL | Миграция на `--mac-*` + `?tab=` | Sprint 5 волна 5.6 | ⬜ PLANNED | §6 волна 5.6 |
| **M-11** 6 монолитов = 44% кода страниц | Декомпозиция по образцу pages/registrar/ | PR-UI-13/14/15 (Sprint 5) | ⬜ PLANNED | §7; Dentist 2 148, Registrar 2 240+, Cashier 2 125; прецедент-образец live |
| **M-12** e2e-скриншоты только cashier+wizard | Phase 0 baseline всех ключевых страниц | Phase 0 + PR-UI-18 | 🟡 PARTIAL | baseline committed (15+ merges стабилен); расширение покрытия 12 экранов → PR-UI-18 |
| **L-1** fallback-hex рассинхрон accent-blue | Единственный источник tokens.css | PR-UI-02 #2814 | ✅ DONE (источник один); остатки контролируются ratchet | live: tokens.css SSOT |
| **L-2** 4 font-family для html + inline-хардкоды шрифтов | `--mac-font-family` canonical | PR-UI-02 + Sprint 5.5 | 🟡 PARTIAL | canonical live; inline-остатки (LoginFormStyled и др.) → 5.5 |
| **L-3** Дубли .sr-only×2 / scrollbar×2 / --ui-font×2 | sr-only канонизирован; остальное — гигиена | C-5 fix + PR-UI-17 | 🟡 PARTIAL | sr-only canonical (tokens.css:926); scrollbar/--ui-font дубли → PR-UI-17 |
| **L-4** ToastContainer themed / мёртвые ветки тем HeaderNew | Чистка | PR-UI-17-track | ⬜ PLANNED | PR-08 follow-up (b) зафиксирован: HeaderNew vestigial glass refs |
| **L-5** /old-login второй вход (PublicApp мёртв) | Удаление | PR-UI-17 (item 13 + AC, v1.8) | ⬜ PLANNED | live grep 29.08: PublicApp 0 импортёров; Login только из PublicApp; legacyRedirectFrom routeRegistry:~225 |
| **L-6** Доки-призраки без archive-notice | Root UI_AUDIT_PLAN.md заменяет ~91 MD | docs-hygiene | 🟡 PARTIAL | SSOT-документ в репо (7cb58984); разметка архивных доков — отдельный docs-шаг |

**Итог v1.8:** 36 findings → **0 ORPHANED**. Подсчёт по первичному статус-бейджу строки (строки с двойным статусом — C-3, H-1, L-1 — считаются по первичному ✅, вторичный виден в строке): ✅ DONE/ACTIVE — **8** (C-1, C-3, C-4, H-1, H-10, M-2, M-3, L-1); 🟡 PARTIAL с владельцем — **13** (C-5, H-4, H-7, H-12, M-1, M-4, M-5, M-6, M-9, M-12, L-2, L-3, L-6); ⬜ PLANNED/TRACKED в спринтах — **12** (C-2, C-6, H-5, H-8, H-9, H-11, M-7, M-8, M-10, M-11, L-4, L-5); 🔁/📌 DECISION-DIVERGENT — **3** (H-2, H-3 — divergent rulings, H-3 кандидат пересмотра в Sprint 5; H-6 — decision-reversed, канон Modal.tsx). 8+13+12+3 = 36. C-6 — единственная находка, бывшая orphaned с 25.08, закрыта введением PR-UI-19.


---

*Этот документ — живой. После каждого PR обновляйте статус в §4 (sprint plan) и file matrix в §3.*
