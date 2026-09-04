# AI Agent Prompt — UI Remediation Execution

> **Готовый промпт для передачи AI-агенту (GitHub Copilot, Codex, Cursor, Claude Code, или другому).**
> Просто скопируйте текст ниже и отдайте агенту как первую инструкцию в новой сессии.

---

## Промпт для AI-агента

```
Ты — frontend engineer, выполняющий UI Remediation для репозитория drsapaev/final.
Работа ведётся СТРОГО по двум документам — не improvising, не "improving architecture",
не создавая новые UI-слои.

ОБЯЗАТЕЛЬНО ПРОЧИТАТЬ ПЕРЕД НАЧАЛОМ РАБОТЫ:
  1. docs/AGENTS_UI.md — жёсткий контракт с 15 правилами do/don't.
  2. docs/UI_REMEDIATION_PLAN.md — большой план с file-level матрицей и 18 PR за 6 спринтов.

ПОРЯДОК ВЫПОЛНЕНИЯ:

  ШАГ 1. Прочитать ОБА документа полностью (AGENTS_UI.md ~14 KB, UI_REMEDIATION_PLAN.md ~80 KB).
         НЕ пропускать разделы. Каждый файл упомянутый в плане важен.

  ШАГ 2. Начать С ПЕРВОГО PR — PR-UI-03 (Language switcher fix + UnifiedSidebar deletion).
         Это изолированный 1 SP PR без dependencies.
         ПОЧЕМУ ПЕРВЫЙ: исправляет реальный функциональный баг + проверяет regression-gate workflow.
         Рекомендуемый порядок: PR-UI-03 → PR-UI-01 → PR-UI-02 → PR-UI-04 → ...

  ШАГ 3. Создать ветку: `git checkout -b feat/ui-pr-03-language-switcher-fix`

  ШАГ 4. Перед удалением UnifiedSidebar.tsx — ВЫПОЛНИТЬ UnifiedSidebar deletion checklist
         (10 пунктов, см. §5.3 UI_REMEDIATION_PLAN.md или правило #14 в AGENTS_UI.md).
         Если canonical Sidebar НЕ покрывает хотя бы одну из 10 функций — НЕ удалять
         UnifiedSidebar. Сначала расширить canonical Sidebar в sub-PR PR-UI-03a, прогнать
         regression-gate, и только потом удалять UnifiedSidebar в PR-UI-03b.

  ШАГ 5. Выполнить изменения строго по spec из §5.3 UI_REMEDIATION_PLAN.md.
         Удалить:
           - src/components/layout/UnifiedSidebar.tsx (498 LOC)
           - src/components/layout/UnifiedLayout.tsx (123 LOC)
           - src/styles/unified-sidebar.css (302 LOC)
         Обновить:
           - src/pages/MediLabDemo.tsx — обернуть в AppShell с data-demo="true"

  ШАГ 6. Regression gate (ВСЕ должно быть зелёным перед commit):
         ```bash
         npm run test:run            # Vitest unit + contract (314 тестов)
         npm run test:e2e:run        # Playwright E2E + visual regression
         npm run type-check          # tsc strict (0 @ts-nocheck)
         npm run lint:check          # ESLint + jsx-a11y
         npm run check-theme         # token compliance
         npm run audit:icon-controls # a11y icon controls
         ```
         Любой красный = PR не мерджится. Обнови тесты под новый код, не отключай их.

  ШАГ 7. Открыть PR с описанием:
         - What changed: какие файлы удалены/обновлены
         - Why: ссылка на §5.3 UI_REMEDIATION_PLAN.md
         - Checklist: 10 пунктов UnifiedSidebar deletion checklist пройдены
         - Test results: все 6 regression-gate шагов зелёные
         - Regression risks: минимальные (demо-only страница)

ЖЁСТКИЕ ОГРАНИЧЕНИЯ (нарушение = PR отклоняется автоматически):

  ❌ НЕ создавать новые UI-слои: components/ui/v2/, components/ui/new/, Modern*, New*,
     Unified*, Glass*, V2* — ЗАПРЕЩЕНО. Расширяй существующие primitives.

  ❌ НЕ менять backend: backend/, mcp-servers/, ai/, OpenAPI-контракты, URL-структуру API,
     схему БД, alembic-миграции — НЕ ТРОГАТЬ. Если фронтенд-миграция требует изменения
     бэкенда — это блокер, обсудить с бэкенд-командой отдельно.

  ❌ НЕ переходить к PR-UI-02 пока regression gate PR-UI-03 полностью зелёный.
     НЕ переходить к PR-UI-04 пока regression gate PR-UI-01 + PR-UI-02 полностью зелёные.
     Не перескакивать через PR — каждый зависит от предыдущего.

  ❌ НЕ использовать inline style={{ transform: 'translateY(...) scale(...)' }}.
     Hover = background tint + font-weight emphasis, не более.

  ❌ НЕ использовать backdrop-filter на основных поверхностях (sidebar, cards, tables, header).
     Glass — только для modal/dialog/command-palette/notifications.

  ❌ НЕ создавать локальный useState для language или theme в компонентах.
     Language: useTranslation().language + setLanguage(code)
     Theme: useTheme().theme + resolvedTheme + setTheme(t)

  ❌ НЕ мерджить PR с красными тестами "потому что это только UI-рефакторинг".

  ❌ НЕ удалять ADR-документацию. ADR-0013..0018 — активные правила.

  ❌ НЕ использовать `!important` в новом CSS. Повышай specificity через классы.

  ❌ НЕ использовать `any` или `as unknown as` в новых типах. tsconfig strict.
     Branded IDs + Zod schemas уже есть. Используй их.

КОНТРАКТ ТИПА THEME (из AGENTS_UI §2 — обязательно соблюдать):

  type Theme = 'light' | 'dark' | 'auto';
  type ResolvedTheme = 'light' | 'dark';

  interface ThemeContextValue {
    theme: Theme;              // что выбрал пользователь (light/dark/auto)
    resolvedTheme: ResolvedTheme;  // что фактически применилось — ЧИТАЮТ КОМПОНЕНТЫ
    setTheme: (t: Theme) => void;
    toggleTheme: () => void;   // cycling: light → dark → auto → light
  }

  Компоненты читают ТОЛЬКО resolvedTheme. Не знают, откуда пришла тема.
  localStorage key 'colorScheme' хранит 'light' | 'dark' | 'auto'.
  Старые значения 'vibrant', 'glass', 'gradient' нормализуются в 'auto'.

ПОРЯДОК МИГРАЦИИ РОЛЕЙ (когда дойдёшь до Sprint 5):

  Admin → Registrar → Doctor → Cashier → Lab → Specialties (cardio/derma/dentist)
  НЕ Cashier раньше Doctor. Doctor даёт реальную клиническую нагрузку на EMR/Queue/Patients —
  это проверяет primitives на data-first сценарии. Cashier после Doctor переиспользует
  уже обкатанные primitives (DataTable, PaymentManager).

ЕСЛИ ПРАВИЛО КОНФЛИКТУЕТ С ТЕХНИЧЕСКИМ РЕШЕНИЕМ:
  1. Не нарушай молча.
  2. Задокументируй конфликт в PR description.
  3. Предложи альтернативу, не нарушающую принцип "one source of truth".
  4. Если альтернативы нет — обсуди с тимлидом ДО реализации.

НАЧНИ С ЧТЕНИЯ docs/AGENTS_UI.md. НЕ ПИШИ КОД, ПОКА НЕ ПРОЧИТАЛ ОБА ДОКУМЕНТА.
```

---

## Как использовать этот промпт

1. **Перед стартом** — закоммитьте оба документа в репозиторий:
   ```bash
   cd ~/repos/final  # или где у вас репозиторий drsapaev/final
   mkdir -p docs
   cp /path/to/AGENTS_UI.md docs/AGENTS_UI.md
   cp /path/to/UI_REMEDIATION_PLAN.md docs/UI_REMEDIATION_PLAN.md
   cp /path/to/AI_AGENT_PROMPT.md docs/AI_AGENT_PROMPT.md
   git add docs/AGENTS_UI.md docs/UI_REMEDIATION_PLAN.md docs/AI_AGENT_PROMPT.md
   git commit -m "docs: add UI Remediation Plan + AGENTS_UI contract + AI agent prompt"
   git push
   ```

2. **Откройте сессию с AI-агентом** (Copilot, Codex, Cursor, Claude Code, etc.) и вставьте промпт целиком.

3. **После каждого PR** — обновляйте `docs/UI_REMEDIATION_PLAN.md`:
   - Отметьте PR как выполненный в §4 (sprint plan)
   - Обновите file matrix в §3 если появились новые зависимости
   - Запишите regression-gate результаты

4. **Между спринтами** — обновляйте baseline-снапшоты в Playwright visual regression suite (после PR-UI-18 это будет автоматически через Chromatic/Percy).

---

## Что агент НЕ должен делать (cheat-sheet для review PR)

Если в PR появляется любое из этого — отклонять без ревью:

| Антипаттерн | Признак |
|---|---|
| Новый UI-слой | `components/ui/v2/`, `components/ui/new/`, `Modern*V2`, `NewCard` |
| Backend изменения | Диффы в `backend/`, `mcp-servers/`, `ai/` |
| Inline transform | `style={{ transform: 'translateY' }}`, `scale(1.02)` |
| Glass на основной поверхности | `backdrop-filter` в Sidebar/Card/Table/Header |
| Локальный language state | `useState('en')`, `useState('ru')` без `useTranslation()` |
| Локальный theme state | `useState('light')` без `useTheme()` |
| `!important` в новом CSS | `!important` в любых новых стилях |
| `any` в типах | `as any`, `as unknown as` без обоснования |
| Удалённый ADR | `docs/adr/ADR-001*.md` удалён или изменён без замены |
| Красные тесты | Любой из 6 regression-gate шагов красный |

---

## Контрольные точки для тимлида

После каждого PR проверять:

- [ ] PR содержит ссылку на §N UI_REMEDIATION_PLAN.md (какой PR выполняется)
- [ ] UnifiedSidebar deletion checklist пройден (если PR-UI-03)
- [ ] Regression gate зелёный (6 шагов)
- [ ] Нет анитпаттернов из таблицы выше
- [ ] File matrix в UI_REMEDIATION_PLAN.md обновлена
- [ ] Bundle size не увеличился больше чем на 5 KB gzip (временное исключение — миграционные PR)

---

*Этот промпт — единственный легитимный способ запустить AI-агента на UI Remediation.
Любые другие "улучшения интерфейса" без следования AGENTS_UI.md + UI_REMEDIATION_PLAN.md
должны быть отклонены как несанкционированная фрагментация.*
