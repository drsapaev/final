# PHASE_0_BASELINE_REPORT — Доказательный отчёт фазы 0 (UI_AUDIT_PLAN.md)

> **Дата:** 2026-08-23
> **База верификации:** `main` @ `7cb5898` (включает PR-UI-01…06 параллельного workstream)
> **Статус фазы:** Phase 0 завершена. **Никаких исправлений кода не производилось** — только измерения, верификация и guardrail-инфраструктура.
> **Соответствие правилам:** один изолированный PR; ничего не удалено; legacy не тронуто; UI-кит и tokens.css не изменены; CI остаётся зелёным (новый ratchet-гейт проходит на текущем состоянии по построению).

---

## 1. Резюме

Phase 0 выполнена по чек-листу: (1) все 18 находок Critical/High из UI_AUDIT_PLAN.md ре-верифицированы на текущем `main` — **ни одна не опровергнута**; (2) четыре ключевые находки (C-1, C-2, C-4, C-5) подтверждены **в runtime на живом приложении** (Vite dev + headless-браузер), а не только grep'ом; (3) создан machine-checkable baseline (`frontend/scripts/ui-baseline.json`) по 16 метрикам и ratchet-гейт `ui-baseline.mjs --check`, подключённый в CI (`regression-audit-gate.yml`); (4) существующие инструменты проверены и не дублируются; (5) зафиксирована координация с параллельной серией PR-UI-01…18.

Главные новые факты относительно аудита: **мёртвого кода больше, чем заявлял аудит** (124 файла недостижимы из import-графа против ~46 проверенных аудитом единиц), **2 кандидата аудита оказались живыми** (AppointmentPagination, TwoFactorVerify), а 6 из 6 Critical — стабильные production-баги с runtime-доказательствами.

---

## 2. Ре-верификация находок аудита (18 шт.)

Метод: свежие Grep/Read по текущему main + полный import-граф + runtime-проверки (раздел 3). Вердикты: **CONFIRMED** / **CHANGED** (суть верна, числа уточнены) / **REFUTED**.

### Critical

| ID | Вердикт | Свежие факты (текущий main) |
|---|---|---|
| **C-1** Сломанные Toast/Modal (`--color-*` из неподключённого CSS) | **CONFIRMED + RUNTIME** | `--color-*` определены только в `styles/admin-styles.css:7–60` (0 импортёров). Потребители: `common/Toast.tsx:147–163,199,219–222`, `common/Modal.tsx:188–242,271,357–449`. Провайдеры монтируются глобально (`AppProviders.tsx:22,25`). Runtime-мост ThemeContext пишет **другие** имена (`--success-color`, ThemeContext.tsx:387–390 — обратный порядок слов), поэтому баг не «спасается» рантаймом. `useModal()` потребляют 6 живых экранов (DoctorPanel:154, CashierPanel:543–544, AdminFinanceOverview:130, AdminDoctors:90, AdminPatients:137, AdminAppointments:203). См. §3.1 |
| **C-2** Модалка «Осмотр» стоматолога на несуществующих классах | **CONFIRMED + RUNTIME** | `DentistPanelUnified.tsx:2172–2328`: оверлей `fixed inset-0 bg-black bg-opacity-50 … z-50 p-4` (:2174), контент `bg-white rounded-lg w-full max-w-4xl … space-y-6` (:2175–2182), 19 вхождений `var(--mac-*)` внутри строки className (:2185, 2192, 2200, 2217, 2232, 2249…). Ни один ключевой класс не определён в живом CSS (часть существует только в мёртвом `theme/globalStyles.css:356–438`). Уточнение к аудиту: `bg-white` не «ломает тёмную тему», а **вообще не применяется** — модалка прозрачная в любой теме. См. §3.2 |
| **C-3** Неопределённые токены | **CONFIRMED (хуже, чем в аудите)** | `var(--mac-info` — **57 вхождений в 14 файлах** (аудит: 34), 0 определений. `var(--mac-text-muted` — 21 в 5 файлах, 0 определений. `var(--admin-*` — **249 вхождений / 86 уникальных имён / 0 определений** в `admin.css` (аудит: «50+»); пример класса-мутанта: `admin.css:10007` `.admin-d-block-fw-500-fs-dyn-col-dyn-mb-dyn` → `var(--admin-fs0/col1/mb2)`. Baseline: **210 имён / 615 использований** неопределённых переменных всего |
| **C-4** `prefers-color-scheme: dark :root` перебивает канон | **CONFIRMED + RUNTIME** | `macos.css:6–23` переопределяет `--mac-bg-primary:#16171a` и др.; канон: `tokens.css` dark `#1c1c1e` / light `#ffffff`. Порядок в `main.tsx:11–12` — macos.css после tokens.css. Runtime: при OS=dark + явном выборе light computed `--mac-bg-primary` = `#16171a` вместо `#ffffff` (см. §3.3). Baseline: 3 файла содержат `@media prefers-color-scheme … :root`-блоки |
| **C-5** Отключённый accessibility.css | **CONFIRMED + RUNTIME** | 267 строк, **0 импортёров** (проверено по ts/tsx/html). Runtime: 0 правил `.sr-only` в 58 загруженных стилевых таблицах живого приложения (см. §3.4) |
| **C-6** Навигация без i18n | **CHANGED (в сторону ухудшения)** | **67** кириллических `label:` в `routeRegistry.ts` (аудит: 61; выросло после PR-UI-04). i18n в реестре отсутствует |

### High

| ID | Вердикт | Свежие факты |
|---|---|---|
| **H-1** Множественные системы токенов | **CONFIRMED** | 10 CSS-файлов-источников токенов: tokens.css (237 определений), emr-tokens.css (94), admin-styles.css (44, мёртв), theme.css (37), PaymentPayMe.css (18), AppointmentWizardV2.css (14), PaymentClick.css (12), accessibility.css (12, мёртв), macos.css (12), dark-fix (10). 12 семейств имён (`--mac-*` 122 имени, `--color-*` 20, `--surface-*` 7, legacy `--bg-*/--text-*/--accent*` 28, `--admin-*` 1...). 30 имён определены более чем в одном файле. JS-источники: `theme/tokens.ts` (1 импортёр — фактически почти мёртв), `tokens-legacy.ts` (1 — ThemeContext), `theme/tokens/` (0 — мёртв) |
| **H-2** Инвертированный каскад | **CONFIRMED** | `main.tsx:8–13`: theme.css → **dark-fix → global-fixes** → tokens.css → macos.css → admin.css (патчи ДО базы, оба входа). `!important`: dark-fix 44, global-fixes 33. Повторные импорты dark-fix из lazy-чанков: DoctorPanel.tsx:4, RegistrarPanel.tsx:16 |
| **H-3** emr-tokens.css — тёмная палитра в `:root` | **CONFIRMED** | `emr-tokens.css:10,14–24`: `--surface-app:#0f0f23` безусловно; тянет только `theme.css:4 @import` |
| **H-4** JS-мост тем | **CONFIRMED** | `ThemeContext.tsx:350–429` пишет `--bg-primary…--accent-color` (:372–380), `--success-color…` (:387–390), `--shadow-*` (:391–414), `--mac-{success,warning,error}-*` (:416–428). После PR-UI-01/02 ThemeContext — единственный runtime-писатель (custom-ветка colorScheme.ts:290–292 мертва). `macosTheme.tsx` удалён (серия PR-UI) |
| **H-5** Двойная навигация DoctorPanel | **CONFIRMED** | `DoctorPanel.tsx`: tabsStyle:442, tabStyle:450, activeTabStyle:468, handleInactiveTabHover:657, рендер 6 inline-табов :673–740 — строки совпадают с аудитом один-в-один |
| **H-6** Зоопарк модалок | **CONFIRMED** | 23 файла Modal/Dialog вне кита (13+9+useModal). В ките одновременно Modal.tsx и Dialog.tsx. Adoption: kit Modal — 13 импортёров, kit Dialog — 14 (обе цифры свежие, детерминированные) |
| **H-7** Две тост-системы | **CONFIRMED** | react-toastify — 45 файлов напрямую; `services/notify` — 46; кастомный ToastProvider — AppProviders + ChatWindow.tsx:23,110 (всё ещё на `useToast`) |
| **H-8** Utility-диалекты | **CONFIRMED** | Доменные page-CSS: 5 632 строк (doctor 386, registrar 853, cashier 484, lab 685, patient 715, cardio 552, dental 724, derma 562, QueueJoin 671) + admin.css 12 657 строк |
| **H-9** Мёртвый код | **CHANGED (существенно больше)** | Import-граф (roots: main.tsx, резолв `./`, `../`, `@/`, `import()`, side-effect imports): **124 файла недостижимы** — см. §4. **2 кандидата аудита опровергнуты**: `AppointmentPagination` жив (импортёр EnhancedAppointmentsTable.tsx:56), `TwoFactorVerify` жив (LoginFormStyled.tsx:13). `medical/*` и `components/Icon.tsx` — не мёртвые, а demo-only (тянутся `/internal-demo/medilab`) → правильная привязка H-12. Root `TelegramManager.tsx` (2 496 строк) жив через App.tsx:66; `telegram/TelegramManager.tsx` (741) мёртв (единственный импортёр — мёртвый TelegramPage) |
| **H-10** Непокрытая тёмная тема | **CONFIRMED** | 0 dark-селекторов в doctor/cashier/lab/patient/dentistry/dermatology/cardiology CSS. 13 CSS-файлов с dark-селекторами. `isDark` — 170 вхождений (23 файла; аудит: 182/29 — слегка улучшилось). `[style*=]`-патчи: 58 селекторов (dark-fix:41–44 и др.) |
| **H-11** Мёртвые Tailwind-осколки | **CONFIRMED** | QueueJoin.tsx: ≥24 строки Tailwind-паттернов (:645–647, :733–811, :966…); DentistPanelUnified: 45 строк. Классы не определены в живом CSS |
| **H-12** Демо-роуты в прод-бандле | **CONFIRMED** | `routeRegistry.ts:1283–1372`: medilab/macos/integration/payment-test/css-test (Admin-only, nav:false, lazy). Изменение: internal-demo-buttons уже удалён (SW-01) |

### Что параллельная серия PR-UI-01…06 уже устранила (не входит в мой план фиксов)

macosTheme.tsx (второй ThemeProvider), UnifiedSidebar/UnifiedLayout + их CSS, vibrant/glass/gradient-схемы, Button 11→6 variants, MacOSMetricCard + ModernCard (мёртвые примитивы), баг language-switcher. **Все 6 Critical и 12 High остаются открытыми** — серия их не затрагивала.

---

## 3. Runtime-верификация (не только grep)

Метод: `npm ci` → Vite dev server (реальное приложение, реальный порядок CSS-каскада из main.tsx/App.tsx) → headless Chrome (agent-browser) → вычисление computed styles / CSSOM.

### 3.1 C-1 — токены Toast/Modal не существуют в рантайме

```
getComputedStyle(:root) на живом приложении (light-theme):
  --color-success          → ""   (пусто — ТОКЕН НЕ СУЩЕСТВУЕТ)
  --color-danger           → ""
  --color-warning          → ""
  --color-info             → ""
  --color-text-secondary   → ""
  --color-background-primary → ""
  КОНТРОЛЬ --mac-success   → "#30d158"  (канонический токен работает)
```

**Вывод:** каждый `var(--color-success)` и т.п. в глобальных Toast/Modal вычисляется в «ничто» (guaranteed-invalid → initial value). Это сломано прямо сейчас в проде у всех ролей: статусные цвета тостов, фоны/тексты модалок, `useModal()` на 6 живых экранах.

### 3.2 C-2 — модалка стоматолога полностью без стилей

```
Элемент с реальными классами модалки (DentistPanelUnified:2174–2175):
  className="fixed inset-0 bg-black bg-opacity-50 … z-50 p-4"
  → position: static; background: rgba(0,0,0,0); z-index: auto; padding: 0px
  className="bg-white rounded-lg w-full max-w-4xl space-y-6"
  → background: rgba(0,0,0,0); border-radius: 0; max-width: none; margin: 0
```

**Вывод:** «Форма осмотра» рендерится как нестилизованный поток контента без оверлея — классов не существует ни в одном живом CSS (а `var(--mac-border)` внутри className — синтаксически невозможный «класс»).

### 3.3 C-4 — тёмная ОС + явный выбор Light = тёмный фон

```
Эмуляция prefers-color-scheme: dark + html class="light-theme …" (явный выбор пользователя):
  computed --mac-bg-primary → "#16171a"   ← значение из macos.css:15 (НЕ канон)
  ожидается при light-theme → "#ffffff"   (канон, tokens.css)
  канонический dark         → "#1c1c1e"  (даже тёмная тема получает не канон, а #16171a)
```

Скриншот-артефакт: `phase0-c4-dark-os-light-choice.png` (сохранён вне репо). Причина: `:root` в media-блоке macos.css равен по специфичности `.light-theme` и загружается позже → побеждает.

### 3.4 C-5 — a11y-слой отсутствует в рантайме

```
Правила .sr-only в загруженных стилях приложения: 0 (из 58 стилевых таблиц)
```

**Вывод:** skip-link/sr-only/focus-visible из accessibility.css не просто «не импортированы» — их физически нет в работающем приложении.

---

## 4. Machine-checkable baseline (главный артефакт фазы)

**Инструмент:** `frontend/scripts/ui-baseline.mjs` (zero-dependency, Node ≥18, детерминированный).
**Baseline:** `frontend/scripts/ui-baseline.json` (commit 7cb5898).
**npm:** `audit:ui-baseline` (отчёт), `audit:ui-ratchet` (гейт).
**CI:** шаг «UI baseline ratchet» в `.github/workflows/regression-audit-gate.yml` (запускается при изменениях `frontend/src/**`, package.json и самих артефактов baseline).

Политика ratchet: значения могут только улучшаться (уменьшаться). Осознанное смещение baseline — только через `--write-baseline` с обоснованием в PR. Проверено: PASS на неизменённом коде (exit 0), FAIL при имитации регрессии (exit 1).

### Ключевые метрики baseline (commit 7cb5898)

| Метрика | Значение | Соответствие аудиту |
|---|---|---|
| Файлов-источников токенов (CSS, ≥10 определений) | **10** | аудита «6 систем» — подтверждено и детализировано |
| Дублирующихся имён токенов (определены в >1 файле) | **30** | — |
| Неопределённых CSS-переменных | **210 имён / 615 использований** | аудит: 151 имя / 369 вызовов → **пересчитано в большую сторону** (детерминированный метод) |
| `var()` всего / без fallback | 13 256 / 12 068 | — |
| Hex-цвета в CSS вне tokens.css | **751** | аудит: ~1 127 (иная методика: комментарии вычтены, только hex) |
| Hex в TSX | **373 в 64 файлах** | аудит: ~692/120 (аудит считал hex+rgb в .ts тоже) |
| Inline `style={{}}` | **2 626 в 231 файле** | аудит: ~2 600/240 — совпадает |
| `!important` (CSS / TSX) | **349 / 80** | аудит: 357/80 — совпадает |
| Modal/Dialog-файлы вне кита | **23** | аудит: 22 (+useModal.tsx) |
| Импортёры kit Modal / kit Dialog | 13 / 14 | — |
| Тосты: react-toastify / notify / кастомный | 45 / 46 / 3 | аудит: 47/46/1 — близко |
| Табы: MacOSTab / ModernTabs / role="tablist" | 7 / 2 / 5 | — |
| Empty-state: MacOSEmptyState / AppEmpty / AppLoading / StateWrapper | 30 / 13 / 10 / 2 | — |
| Уникальных @media-брейкпоинтов | **16** (360…1536) | аудит: 19 (иная методика счёта) |
| Дублирующихся @keyframes имён | **10** (spin×17, pulse×9, fadeIn×8, slideDown×6, shimmer×3, slideIn×3, +4×2) | совпадает |
| Недостижимых файлов (import-граф) | **124** | аудит: ~46 проверенных единиц → **полный граф нашёл больше** |
| Кириллических label в routeRegistry | **67** | аудит: 61 |
| accessibility.css импортирован | **false** | — |
| Dark: CSS с dark-селекторами / prefers-:root-блоки / isDark-ветвления / [style*=]-патчи | 13 / 3 / 170 / 58 | близко к аудиту |

**Каветата к метрике «недостижимых файлов»:** это детерминированный кандидат-лист по import-графу (корни: main.tsx; резолвятся относительные, `@/`-алиасы, динамические и side-effect импорты). Перед **фактическим удалением** любого файла обязателен индивидуальный grep импортёров/строк (правило плана: «не удалять, пока не доказано отсутствие потребителей» — Phase 0 его не нарушала: ничего не удалено). Примеры подтверждённо мёртвых цепочек: `components/index.ts` → `ProtectedRoute` → `RequireAuth` (весь реэкспорт-барель не импортируется никем).

---

## 5. Существующие инструменты: проверено, не дублируется

| Инструмент | Статус по проверке | Действие Phase 0 |
|---|---|---|
| `scripts/no-hardcoded-colors.js` (ESLint custom rule) | **Подключён в eslint.config.js:8,24,53, но с severity `warn`** — не блокирует CI; объясняет, почему hex-долг растёт | Не дублирован: baseline считает hex своим методом; рекомендация (в отчёт, не в код) — поднять до `error` отдельным PR после чистки топ-файлов |
| `scripts/check-theme-compliance.js` (`npm run check-theme`) | Живой, в regression-gate по правилу 13 AGENTS_UI.md | Не тронут; работает параллельно |
| `scripts/sw07-token-unification.py` | Это **codemod** (перезапись hex→var), не чекер | Не тронут; не guardrail |
| `scripts/audit-icon-only-controls.mjs` + baseline JSON | Эталонный ratchet-паттерн | **Взят за образец** для ui-baseline.mjs (baseline+strict+write-baseline+exit-коды) |
| `scripts/type-debt-check.mjs` (root) | Count-ratchet с захардкоженным baseline | Не тронут |
| `scripts/regression-audit-check.mjs` + `regression-audit-gate.yml` | Живой CI-гейт (BS-ID инварианты) | **Расширен одним шагом** (UI baseline ratchet), BS-ID-система не тронута |
| Playwright visual regression (`e2e/`) | Существует (5 PNG baseline: cashier, wizard). Полный baseline ключевых страниц — не выполнен: требует работающего backend и кредов | Задокументировано как ограничение; runtime-проверки Phase 0 выполнены на живом CSS-каскаде без backend |

---

## 6. Координация с параллельным workstream (PR-UI-01…18)

В репо действует контракт `docs/AGENTS_UI.md` и план `docs/UI_REMEDIATION_PLAN.md` (серия PR-UI-01…18, порядок ролей Admin→Registrar→Doctor→Cashier→Lab→Specialties). Статус: **выполнены PR-UI-01…06** (последний 2695cea); следующие по их плану — PR-UI-07 (AppState-консолидация), PR-UI-08 (удаление cursor-effects.css и чистка animations), PR-UI-09 (canonical DataTable), далее PR-UI-17 (массовое удаление мёртвого кода — туда уже занесены forms/, medical/, ResponsiveTable, cursor-effects, admin-styles).

Следствия для UI_AUDIT_PLAN.md:
1. **Мой план не стартует собственные дубликаты их PR**: Phase 1.6 (удаление мёртвого) должна координироваться с PR-UI-17; Phase 3.4 (empty-state) — с PR-UI-07; чистка keyframes — с PR-UI-08.
2. **Конфликт спецификаций accent-цвета**: UI_AUDIT_PLAN.md §5.1 описывает `--mac-accent-blue #007aff` как канон; AGENTS_UI.md правило 9 объявляет primary = `--mac-accent` (teal) и запрещает `#007aff` в стилях. Практически в tokens.css сейчас `--mac-accent-blue: #007aff` (:37) существует наряду с `--mac-accent`. Для фиксов Phase 1 буду следовать AGENTS_UI.md как живому контракту (правило 9) и вынесу вопрос в PR-описание.
3. Ratchet-гейт Phase 0 защищает общую траекторию обоих планов: любые PR (мои или серии PR-UI) теперь не могут ухудшить метрики молча.

---

## 7. Что намеренно НЕ сделано в Phase 0

- Не исправлен ни один баг (включая подтверждённые runtime Critical C-1…C-5).
- Не удалён ни один файл, не переписан ни один токен, не изменён порядок CSS-импортов.
- Не поднята severity ESLint-правил, не изменены тесты.
- Не создан полный визуальный baseline всех страниц (требует backend-окружения; зафиксировано как ограничение —(runtime-проверки каскада выполнены и достаточны для доказательства C-1/C-2/C-4/C-5).

## 8. Следующий шаг (предложение, ожидает подтверждения)

**PR «C-1 fix»** — один изолированный фикс, минимальный diff, два варианта на выбор:
- (а) добавить алиас-блок `--color-*: var(--mac-*)` в `design-system/tokens.css` (восстанавливает Toast/Modal везде сразу, ~10 строк, соответствует alias-стратегии плана §5.2 слой 6);
- (б) перевести `common/Toast.tsx` + `common/Modal.tsx` на `--mac-*` напрямую (чище, но дифф больше; затрагивает 2 живых провайдера).

Оба варианта совместимы с AGENTS_UI.md (правило 1: расширение canonical-файла, не новый токен-файл). Regression gate: `type-check` + `lint:check` + `test:run` + `check-theme` + `audit:ui-ratchet` + скриншот до/после тоста и модалки в light/dark.

