# AGENTS_UI.md — AI Agent Contract for UI Remediation

> **Жёсткий контракт для любого AI-агента (или человека), реализующего миграцию UI в репозитории `drsapaev/final`.**
> Прочитать ПЕРЕД началом работы. Нарушение любого правила = PR отклоняется без ревью.

---

## Контекст

Фронтенд clinic-системы накопил 5 параллельных UI-слоёв (macOS, Modern*, MUI-legacy, Tailwind-классы, Unified*), 2 ThemeProvider, 2 accent-blue, 6 color schemes, 8 Card-типов, 6 Table-реализаций, 3 модели навигации. Цель миграции — **Medical Minimalism**: один визуальный язык, одна тема, один shell, одни primitives. НЕ создавать новых слоёв.

**Принцип:** Layout Restructure, а не очередной косметический слой поверх существующих.

---

## 13 правил «Do / Don't»

### 1. ONE design system

- ✅ **DO:** Использовать `src/design-system/tokens.css` (после миграции из `macos-tokens.css`) как единственный источник CSS-переменных.
- ❌ **DON'T:** Создавать новые `*-tokens.css`, `*-theme.css`, `unified-theme.ts` файлы. Если нужно расширить токены — добавляй в существующий canonical-файл.

### 2. ONE ThemeProvider

- ✅ **DO:** Использовать `useTheme()` из `src/contexts/ThemeContext.tsx` во всех случаях. Тема имеет **3 состояния** + 1 вычисляемое:
  ```ts
  type Theme = 'light' | 'dark' | 'auto';
  type ResolvedTheme = 'light' | 'dark';  // вычисляется из Theme + prefers-color-scheme
  
  interface ThemeContextValue {
    theme: Theme;              // что выбрал пользователь (light/dark/auto)
    resolvedTheme: ResolvedTheme;  // что фактически применилось (light/dark) — читают компоненты
    setTheme: (t: Theme) => void;
    toggleTheme: () => void;  // cycling: light → dark → auto → light
  }
  ```
  Компоненты читают **только `resolvedTheme`** — они не знают, пришла ли тема из `light`/`dark`/`auto`. Это убирает dual-truth: `--mac-bg-primary` всегда соответствует `resolvedTheme`, без задержки на event dispatch.
- ❌ **DON'T:** Использовать `useMacOSTheme()` или `MacOSThemeProvider`. После PR-UI-01 файл `src/theme/macosTheme.tsx` удалён, его функционал слит в ThemeContext. Также НЕ использовать паттерн `theme: 'light' | 'dark'` + отдельный `systemPreference` — это снова создаёт два источника правды. Только `theme: 'light' | 'dark' | 'auto'` + `resolvedTheme`.
- ⚠️ **Migration note:** localStorage key `colorScheme` хранит `'light' | 'dark' | 'auto'`. Старые значения `'vibrant'`, `'glass'`, `'gradient'` (если есть у пользователей) нормализуются в `'auto'` при первом заходе после деплоя PR-UI-01.

### 3. ONE color scheme set

- ✅ **DO:** Поддерживать `light`, `dark`, `auto` (через `prefers-color-scheme`) как canonical schemes.
- ❌ **DON'T:** Активировать `vibrant`, `glass`, `gradient` вне `/internal-demo/*` роутов. Их CSS можно оставить в `styles/macos.css` под `@media (internal-demo)`, но в `HeaderNew.tsx`-меню они не появляются для production-пользователей.

### 4. ONE AppShell

- ✅ **DO:** Все авторизованные роуты используют `AppShell` из `src/App.tsx` (header + sidebar + main). Sidebar получает items из `routeRegistry.SIDEBAR_PRESETS[role]`.
- ❌ **DON'T:** Создавать параллельные `UnifiedSidebar`, `UnifiedLayout`, `Nav`, `ModernTabs`-as-navigation. После PR-UI-04 они удалены.

### 5. ONE navigation model

- ✅ **DO:** Все роли (Admin, Registrar, Doctor, Cashier, Lab, specialties) получают навигацию из одного и того же `SIDEBAR_PRESETS` registry, отфильтрованного по `profile.roles`.
- ❌ **DON'T:** Хардкодить кнопки навигации в `HeaderNew.tsx`. Header = brand + search + notifications + profile + language + theme. НЕ навигация.
- ⚠️ **Shared-clinical workspace boundary (PR-UI-04c audit, 23.08.2026):**
  `sidebarPreset: 'default'` is the canonical navigation boundary for shared clinical routes (`/clinical/appointments`, `/clinical/search`, `/clinical/scheduler`, `/clinical/pickup`). Role-specific presets (`registrar`, `cashier`, `doctor`, `lab`) apply to role workspaces only. The `default` preset provides RBAC-filtered shared clinical navigation via `getClinicalNavRoutes(profile)` — each role sees only the clinical routes it can access. **Do NOT override `default` with a role-specific preset based solely on the user's role.** This is a verified architectural decision, not a bug.

### 6. ONE icon system

- ✅ **DO:** Использовать `lucide-react` (единая библиотека, уже в package.json) во всех компонентах.
- ❌ **DON'T:** Использовать `src/components/Icon.tsx` (60-LOC legacy с `assets/iconsMap`). После PR-UI-17 файл удалён. Также не использовать `src/components/ui/macos/Icon.tsx` (546-LOC SF Symbols wrapper) — мигрировать на прямые `lucide-react` импорты.

### 7. ONE spacing scale

- ✅ **DO:** Использовать `--mac-spacing-1` (4px) → `--mac-spacing-16` (64px) из `tokens.css`.
- ❌ **DON'T:** Хардкодить `3px`, `5px`, `7px`, `13px`, `18px` в inline-стилях или CSS. Stylelint-правило `declaration-property-value-allowed-list` (PR-UI-17) отклонит такие значения.

### 8. ONE typography scale

- ✅ **DO:** Использовать `--mac-font-size-xs/sm/base/lg/xl/2xl/3xl` (11/12/13/15/17/22/28px).
- ❌ **DON'T:** Хардкодить `14px`, `16px`, `20px`. Если нужно новое значение — добавляй в tokens.css с семантическим именем (например `--font-size-caption-lg`).

### 9. ONE semantic color system

- ✅ **DO:** Использовать токены: `--mac-accent` (primary teal), `--mac-success`, `--mac-warning`, `--mac-error`, `--mac-info`. Accent цвета ролей: Admin=blue, Doctor=teal, Lab=purple, Cashier=amber, Registrar=blue.
- ❌ **DON'T:** Использовать `#007aff` (старый macOS blue) напрямую в стилях. Только через `var(--mac-accent)`. Специальности (cardio=red, derma=violet, dentist=blue) — как ДОПОЛНИТЕЛЬНЫЙ сигнал через иконку/бейдж, не как основной цвет UI.

### 10. NO Modern* / New* / Unified* / Glass* alternatives

- ✅ **DO:** Заменять `ModernCard`, `ModernDialog`, `ModernInput`, `UnifiedCard`, `UnifiedLayout`, `UnifiedSidebar`, `MacOSCard`, `MacOSStatCard`, `MacOSMetricCard`, `MetricCard`, `MedicalCard`, `PatientCard`, `StatCard` на canonical: `Card`, `StatCard`, `DataCard` (3 типа).
- ❌ **DON'T:** Создавать `NewButton`, `UnifiedButton`, `ModernButtonV2`, `GlassCard` и т.п. Если существующий `Button` не подходит — расширяй его variant enum, не создавай параллельный компонент.

### 11. NO backend contract modifications

- ✅ **DO:** Мигрировать только frontend: `src/components/`, `src/contexts/`, `src/styles/`, `src/routing/`, `src/pages/`, `src/i18n/`, `src/theme/`.
- ❌ **DON'T:** Трогать `backend/`, `mcp-servers/`, `ai/`, OpenAPI-контракты, URL-структуру API, схему БД, alembic-миграции. Если фронтенд-миграция требует изменения бэкенда — это блокер, обсудить с бэкенд-командой отдельно.

### 12. Migrate ONE role first, then next

- ✅ **DO:** Мигрировать роли последовательно в порядке: **Admin → Registrar → Doctor → Cashier → Lab → Specialties** (cardio/derma/dentist).
  
  Обоснование порядка (обновлено):
  - **Admin** — самое широкое покрытие каноничных primitives (38 экранов, Forms, Tables, Charts, Settings). Миграция Admin первой проверяет, что primitives выдерживают разнообразие; если Button/Card/Table не покрывают admin-use-case, лучше узнать сейчас, а не на 5-й роли.
  - **Registrar** — максимальная нагрузка на Wizard (3 154 LOC god-компонент), PaymentManager, queue, patients, batch API. Проверяет, что primitives выдерживают сложные формы + многошаговые flow.
  - **Doctor** — ДО Cashier, потому что Doctor даёт реальную клиническую нагрузку на EMR (медкарта, 16 секций), QueueTable (keyboard nav), Patient cards, specialty-routing. Это проверяет primitives на data-first сценарии — то, ради чего делается Medical Minimalism.
  - **Cashier** — после Doctor, потому что Cashier переиспользует primitives, уже обкатанные на Doctor (DataTable из RefundRequestsTable ≈ QueueTable, PaymentManager уже мигрирован в Registrar). CashierPanel — 2 125 LOC god-компонент, но структурно проще RegistrarPanel.
  - **Lab** — компактная панель (815 LOC), использует уже знакомые primitives.
  - **Specialties** (cardio/derma/dentist) — последними, потому что требуют specialty-color как дополнительного сигнала. К этому моменту canonical primitives уже стабильны, и добавление specialty-tint не сломает архитектуру.
  
  Между миграциями — полный regression-gate (Playwright visual + functional + a11y + load).
- ❌ **DON'T:** Мигрировать все роли параллельно. Это создаёт комбинаторный взрыв тестирования и почти гарантирует регрессии.

### 13. Visual + functional regression gate после КАЖДОГО PR

- ✅ **DO:** После каждого PR запускать: `npm run test` (Vitest unit), `npm run test:e2e:run` (Playwright), `npm run type-check` (tsc strict), `npm run lint:check` (ESLint + jsx-a11y), `npm run check-theme` (token compliance), `npm run audit:icon-controls` (a11y). Все должно быть зелёным перед merge.
- ❌ **DON'T:** Мерджить PR с красными тестами «потому что это только UI-рефакторинг». UI-регрессии сложнее ловить в продакшене — каждый сломанный flow = потерянный пациент в клинике.

### 14. UnifiedSidebar deletion checklist (обязателен перед удалением в PR-UI-03)

Перед удалением `src/components/layout/UnifiedSidebar.tsx` убедиться, что canonical `Sidebar` (из `src/components/ui/macos/Sidebar.tsx`) покрывает ВСЕ 10 функций UnifiedSidebar. Если хотя бы одна не покрыта — НЕ удалять UnifiedSidebar, пока не добавлена в canonical.

| # | Функция | Где проверить в canonical Sidebar | Acceptance |
|---|---|---|---|
| 1 | Role filtering (RBAC-driven items) | `SIDEBAR_PRESETS[role]` → `routeSelectors.getRouteChromeState` | Все 9 ролей (Admin, Registrar, Doctor, Cashier, Lab, cardio/derma/dentist, Patient) получают корректный набор пунктов |
| 2 | Active route highlight | `activeItem` prop + `useLocation().pathname` matching | Текущий пункт подсвечен при прямой навигации и при reload страницы |
| 3 | Collapsed state (icon-only mode) | `collapsed`/`defaultCollapsed` props + localStorage persistence | Состояние сохраняется между сессиями; иконки видны в collapsed режиме |
| 4 | Mobile behavior (overlay drawer) | `App.tsx:246-322` mobile-sidebar logic (после PR-UI-04 — overlay drawer pattern) | На 375px viewport sidebar скрыт по умолчанию; hamburger открывает overlay |
| 5 | Theme toggle | `useTheme().toggleTheme()` из canonical ThemeContext | Клик переключает light↔dark↔auto; иконка обновляется мгновенно |
| 6 | Language switch | `useTranslation().language` + `setLanguage(code)` (НЕ локальный useState!) | Кнопка EN/RU/UZ синхронизирована с фактическим языком UI |
| 7 | Profile display (avatar + name) | `auth.getState().profile` + аватар (initials или изображение) | В collapsed режиме показывает только аватар с tooltip «Dr. Sapaev / Cardiologist» |
| 8 | Logout | `auth.clearToken()` + redirect на `/login` (через `useNavigate`) | После logout пользователь оказывается на /login, а не остаётся на текущей странице |
| 9 | Keyboard navigation | `tabIndex`, `aria-label`, `:focus-visible` outline на каждом пункте | Tab перемещает фокус по пунктам; Enter активирует; Escape закрывает overlay |
| 10 | ARIA (aria-label, aria-current, role="navigation") | `aria-label="Главное меню"`, `aria-current="page"` на активном пункте | Screen reader озвучивает: «Главное меню, навигация, текущий раздел: Очередь» |

**Если canonical Sidebar не покрывает хотя бы одну функцию из списка — это блокер для PR-UI-03.** Сначала расширить canonical Sidebar в отдельном sub-PR (например PR-UI-03a), прогнать regression-gate, и только потом удалять UnifiedSidebar в PR-UI-03b.

### 15. Language switcher — критический P0 bugfix

Баг локального `useState('en')` в UnifiedSidebar (строки 31, 74) — это не стилистическая мелочь, а реальная функциональная поломка: пользователь думает, что сменил язык, но i18next не меняется, и весь остальной UI остаётся на прежнем языке. Это подрывает доверие к интерфейсу.

- ✅ **DO:** Запустить PR-UI-03 (Language switcher fix + UnifiedSidebar deletion) **до** PR-UI-01 если возможно. Это изолированный 1 SP PR без dependencies — его можно выполнить за полдня и получить быструю победу до большой ThemeProvider миграции. Это также проверит, что regression-gate workflow работает, перед запуском более рискованных изменений.
- ✅ **DO:** Если PR-UI-03 выполняется после PR-UI-01 — убедиться, что новый canonical ThemeProvider не зависит от UnifiedSidebar (он не должен, но проверить grep'ом `useTheme\|ThemeContext` в UnifiedSidebar.tsx).
- ❌ **DON'T:** Чинить UnifiedSidebar «на месте» (минимальный фикс `useState('en')` → `useTranslation().language`) — это оставит мёртвый код. Лучше удалить файл целиком, поскольку он используется только в MediLabDemo, и мигрировать MediLabDemo на canonical AppShell + Sidebar.

---

1. **Прочитать `docs/UI_REMEDIATION_PLAN.md`** полностью (большой документ с file-level матрицей).
2. **Выбрать PR из sprint plan** (PR-UI-01 → PR-UI-18). Не перескакивать — каждый зависит от предыдущего.
3. **Создать ветку:** `git checkout -b feat/ui-pr-XX-short-name` (например `feat/ui-pr-01-unified-theme-provider`).
4. **Реализовать изменения** строго по spec из плана. Если spec противоречит AGENTS_UI — написать в PR description, какой пункт конфликта, и предложить решение.
5. **Прогнать regression gate** локально (см. правило 13).
6. **Открыть PR** с описанием: что изменено, какие файлы удалены/добавлены, какие тесты добавлены, какие regression-риски.
7. **После merge:** обновить `docs/UI_REMEDIATION_PLAN.md` — отметить PR как выполненный, обновить file matrix если появились новые зависимости.

---

## Антипаттерны (автоматический отказ от PR)

| Антипаттерн | Почему запрещено |
|---|---|
| Создание `components/ui/v2/` или `components/ui/new/` | Снова фрагментация. Расширяй существующий `components/ui/`. |
| Использование `!important` в новом CSS | Старая болезнь `sidebar-buttons.css`. Если нужно переопределить — повышай specificity через классы, не через `!important`. |
| Inline `style={{ transform: 'translateY(-2px) scale(1.02)' }}` | "Прыгающий" hover — user явно запретил. Hover = `background` tint + `font-weight` emphasis, не более. |
| Inline `style={{ backdropFilter: 'blur(...)' }}` на основной поверхности | Glass — только для modals, popovers, command palette. Не для sidebar, не для cards, не для таблиц. |
| Локальный `useState('en')` для language в любом компоненте | Этот баг уже был в `UnifiedSidebar`. Language = `useTranslation().language`, change = `useTranslation().setLanguage(code)`. |
| Локальная подписка на `colorSchemeChanged` event в компонентах | Это симптом, что ThemeProvider не делает свою работу. Компонент должен читать `useTheme().colorScheme`, а не слушать window-events. |
| `any` или `as unknown as` в новых типах | tsconfig strict. Branded IDs + Zod schemas уже есть. Используй их. |
| Удаление ADR-документации без замены | ADR-0013..0018 — активные правила. Если миграция делает ADR неактуальным — обнови ADR, не удаляй. |

---

## Что НЕ делать в рамках UI-миграции

- ❌ Мигрировать на Radix UI / shadcn (A1 в priority matrix — impact 4.0, effort 9.0, не окупается)
- ❌ Переходить на CSS-in-JS / styled-components (A2 — потеря SSR-совместимости)
- ❌ Мигрировать React Router 6 → TanStack Router (A3 — текущий registry-паттерн решает задачу)
- ❌ Менять сборщик Vite → Next.js / Remix (out of scope)
- ❌ Трогать TypeScript strict-режим или понижать `strict: true` (это база качества)
- ❌ Удалять тесты «потому что они мешают рефакторингу» — обновляй тесты под новый код

---

## Связанные документы

- `docs/UI_REMEDIATION_PLAN.md` — большой план с file-level матрицей delete/merge/keep/migrate
- `frontend/DESIGN_SYSTEM.md` — текущая документация дизайн-системы (будет обновлена в PR-UI-02)
- `frontend/AGENTS.md` — общий операционный rules для AI-агентов (UI-контракт — надстройка над ним)
- `frontend/ADR-0013..0018` — архитектурные решения (state management, error taxonomy, validation)
- `frontend/src/routing/routeRegistry.ts` — реестр маршрутов (не трогать без необходимости)

---

## Контакты и эскалация

Если любое правило из этого контракта блокирует разумное техническое решение:
1. Не нарушай молча — задокументируй конфликт в PR description
2. Предложи альтернативу, не нарушающую принцип «one source of truth»
3. Если альтернативы нет — обсуди с тимлидом до реализации

**Этот контракт — не рекомендация, а gate.** PR без соблюдения правил будет отклонён автоматически.
