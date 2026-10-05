# План исправления и упрощения административной настройки очередей

**Версия:** 3.7 — T08.3.2 / #3600 merged; deterministic-clock P2 follow-up is PR #3607.
**Создан:** 30 сентября 2026. **Обновлён:** 5 октября 2026, 17:38 Asia/Tashkent.
**Current task:** T08.3.2 post-merge P2 follow-up — make four QR-session PostgreSQL tests independent of wall-clock time.
**Current worktree:** `C:\Users\DrSapaev\.codex\worktrees\aqs-t08-3-2-clockfix\final`; branch `codex/aqs-T08.3.2-clockfix`; base `origin/main` = `ba03fdfb8d14d38a68a2d16df93145562cd87c63`.
**Scope:** one focused PG integration module plus these plan/checkpoint journals. Runtime, model, migration, feature flag, frontend, Docker/Compose and staging/production changes are not authorized by this subtask. V1 creation remains default-off.
> The T08.2c worktree, PR-open status and pending-check metadata below are historical and superseded by the confirmed #3596 merge.
**Основание аудита:** `main`, `07ea63368989290318212635a7ab3a3bc2ed756d`.
**Историческая база T00:** `8bb1bdff5ce68627fe29eb227c03bb7ea0f9d1be`.
**Последний подтверждённый runtime merge:** `7f3b751241eaa1f9a0ffdf07fff09cbdec32eba7`, PR #3596 / T08.2c. Последующий T08.3.1 PR #3599 добавил PostgreSQL tests и был merged as `a452c54e5851611476c1b2ac3e3298aeff467eca`.
**Последующий test-only merge:** PR #3600 / T08.3.2 merged at `b3bd5272389da88513cc1ac23985b390489554f9`; deterministic-clock P2 follow-up is [PR #3607](https://github.com/drsapaev/final/pull/3607), with exact-head checks pending.
> Следующие две строки — исторический снимок метаданных T08.2c, оставленный для прослеживаемости; текущие ветка и статус указаны выше.
**Текущий worktree:** `C:\final\_wt_aqs_t082c_availability`; ветка `codex/aqs-T08.2c-availability`; база `9b8296f8e090a2d6f6e0c70eb78e4f00f4e6d80e`; PR [#3596](https://github.com/drsapaev/final/pull/3596). Report implementation `718d4d65c5717528e8a93fb819fdf328c63bf772`; future-date compatibility fix `b6c3973d11a450169c1e5ad04c4dbf5d47ac33d8`; OpenAPI EOF parity fix `f8012a1cd8bea673f218f2c873b197c1940b24eb`. Focused local checks pass (85 unit/OpenAPI, 4 selected integration). The docs-freshness CI failure on `fd9b1c793` was due to a final CRLF in the generated snapshot; it is removed to match exact app serialization. New exact-head checks pending.

> **T00–T07, T08.1a, T08.1b, T08.2a, T08.2b, T08.2c, T08.3.1 and T08.3.2 — MERGED; T08.3.2-P2 clock follow-up — PR_OPEN (#3607); T08.3.3 and T09–T18 — PLANNED.** PR #3600 / T08.3.2 merged at `b3bd5272389da88513cc1ac23985b390489554f9`. The follow-up freezes the queue service's clinic clock at midday and seeds the same clinic day in its four QR v1 tests. The PostgreSQL module passed 11 tests with no skips; static checks passed; PR body quality validation passed. Exact PR HEAD `d4d1524aa96f7260825b6f0caf1b9cb724044490` had 10 successful checks, 4 skipped, 0 failed; a later evidence-only checkpoint will require fresh checks. See the current PROGRESS/RESUME checkpoint and `EVIDENCE.md#t0832-clock-follow-up-pr-3607`.
> Принятый deferral staging для #3543 не является PASS и не распространяется на следующие PR. Feature flag создания v1 остаётся выключенным; production activation и deploy не разрешены.

**Обязательный вход для агента:** [RESUME.md](admin-queue-simplification/RESUME.md).
**Текущая точка:** [PROGRESS.md](admin-queue-simplification/PROGRESS.md).
**Решения:** [DECISIONS.md](admin-queue-simplification/DECISIONS.md).
**Доказательства:** [EVIDENCE.md](admin-queue-simplification/EVIDENCE.md).

Подробная версия 1.1 ранее осталась незакоммиченной в worktree T03. Версии 1.2–1.7 сохранили последовательные checkpoints T03–T06.2. Версия 1.8 подтвердила merge T06.2; версии 2.0–2.3 сохранили T07/T08 history. Версия 2.4 подтверждает слияние T07 и T08.1a и фиксирует границы T08.1b. Исторические evidence сохраняются. Пропущенные staging/browser/PG проверки остаются NOT_RUN и не считаются приёмкой.

## 1. Цель и границы

Согласовать реальные правила очереди и собрать понятный процесс настройки направления. Администратор видит услуги, исполнителей, кабинеты, доступность записи и конкретные причины несоответствий в одном контексте.

Конечная навигация:

- «Направления и очереди» — `/admin/setup-directions`, основной раздел.
- «Общие правила очереди» — `/admin/queue-settings`.
- Каталог услуг остаётся самостоятельной рабочей задачей.
- `/admin/services?servicesTab=queue-profiles` и `/admin/queue-cabinet-management` остаются совместимыми входами.

Не входят: перенос владельца очереди, объединение очередей, перенумерация, изменение клинического lifecycle, новая ролевая система, новая сущность `Direction`, отдельный BFF-сервис и таблица прогресса настройки.

### Settings

- Testing: yes — целевые проверки этапа, обязательные PG/контрактные проверки и синтетическая браузерная приёмка.
- Logging: standard — безопасные IDs/причины отказа; без PHI, токенов и полных payload.
- Docs: yes — checkpoint/evidence и операторские инструкции входят в PR соответствующего поведения.
- Runtime context: production Windows `C:\final`, backend `18000`; dev frontend `5173`; isolated WSL staging backend `18001`, frontend `18080`, PostgreSQL `55432`. Изоляцию проверять фактически, не только по номеру порта.

### Roadmap Linkage

Milestone: `none`. Продолжение согласованного отдельного плана. Общий roadmap не меняется; документ хранит собственные этапы и доказательства.

## 2. Решения пользователя и канонический контракт

| ID | Решение | Обязательное поведение |
|---|---|---|
| D1 | Лимит — успешные онлайн-записи за день | Отмена, завершение и неявка не освобождают лимит. Регистратура учитывается отдельно. |
| D2 | Обычная смена кабинета действует на будущие очереди | Созданные очереди не меняются; сегодняшнее назначение — отдельная preview/apply-команда с аудитом. |
| D3 | Время окончания закрывает самозапись | Новые онлайн-записи запрещены; существующие пациенты обслуживаются. |
| D4 | Общая вкладка разных направлений — внутренний обзор | Пациент записывается через конкретное направление. |
| D5 | Новые направления публикуются явно | Настройка и проверка, затем «Опубликовать». |

Уточнения реализации:

1. Квота принадлежит канонической дневной очереди: врач + день + тег либо ресурс + день. Doctor ID и resource ID типизированы и не смешиваются.
2. Replay уже зафиксированного результата не расходует квоту. Служебное копирование, перенос и добавление услуги не являются новой самостоятельной онлайн-записью.
3. Нулевой лимит запрещает новые онлайн-записи; он не заменяется default. Отсутствующее значение и ноль различаются.
4. Внутри команды использовать согласованный snapshot defaults. Новые настройки не переписывают параметры созданной дневной очереди.
5. Раннее ручное закрытие сохраняется. Cutoff — настроенное окончание либо уже выполненное раннее закрытие; существующие записи остаются обслуживаемыми.
6. Неработающие параметры отделений не подключать к runtime автоматически. Стартовый номер `1` сохраняет существующий смысл наследования; UI объясняет его.
7. Legacy historical online count неизвестен. Миграционный технический `0` не является доказанным количеством выдач.
8. Существующие `is_active=false` сохраняются: прежнюю причину отключения нельзя восстановить по догадке.
9. Частичный результат многокомпонентной записи сохраняет действующий контракт. Не вводить общее «всё или ничего» для всех путей.

Инварианты из [DIRECTION_CONTRACT.md](registrar-queue-remediation/DIRECTION_CONTRACT.md) и [ADR-001](../../docs/adr/ADR-001-queue-ownership-and-specialty-architecture.md):

- `Doctor`, `QueueResource`, `QueueProfile`, `DailyQueue` остаются разными сущностями.
- У очереди ровно один владелец: врач или ресурс. Профиль может агрегировать очереди и не получает собственную нумерацию.
- Кабинет — место обслуживания. Default владельца и кабинет snapshot дневной очереди — разные факты.
- Выданные номера, `queue_time`, история, статусы пациентов и клинические записи не переписываются.
- Общий QR клиники, постоянные адреса, TTL, ограничения доступа, токены и идемпотентность сохраняются.

Новые продуктовые решения записывать в DECISIONS с источником авторизации. Технический выбор не выдавать за решение пользователя.

## 3. Фактическое состояние и ближайший шаг

| Этап | Фактическое состояние | Подтверждение |
|---|---|---|
| T00 | MERGED | #3536, `bae927f5c88010808d9091e7f47d09bbfdfa1005` |
| T01 | MERGED | #3537, `967bd398c14bce4b835bd5be1205532387e2a909` |
| T02 | MERGED | #3538, `b4ba6320797f056da19bbdc5cc672b3a97d2091e` |
| T03 | MERGED | [#3540](https://github.com/drsapaev/final/pull/3540), `1e781da72bd927926b538b139a6c251cd09848b5` |
| T04 | MERGED | [#3541](https://github.com/drsapaev/final/pull/3541), `ecc14b05411c7e7b54efca2966416cd6a69df37c` |
| T05 | MERGED | [#3543](https://github.com/drsapaev/final/pull/3543), `fd53206f03b0361de6fc345f53b2bacf4195845c` |
| T06.1 | MERGED | [#3545](https://github.com/drsapaev/final/pull/3545), `e8f585ab0a51e256fa638fe56c0582eff0bbafc6` |
| T06.2 | MERGED | [PR #3546](https://github.com/drsapaev/final/pull/3546), `b804a71a6bad22400324e2236a3221317eac3158` |
| T07 | PR_OPEN | `codex/aqs-T07-admission-window` / [PR #3557](https://github.com/drsapaev/final/pull/3557), worktree `C:\final\_wt_aqs_t07_window`, based on `3a776133` |
| T08–T18 | PLANNED | Runtime-реализация не начата |

Для #3543 проверен актуальный HEAD `c04f41021bef5f8c306b9668cbb1c4b9afef2cc1`: применимые Backend tests, Code Quality, parity, Context Boundary, PR Required Gate, security и PR Review Quality Gate — PASS. [Backend CI run 36851998918](https://github.com/drsapaev/final/actions/runs/36851998918). Path-aware skipped frontend/integration/staging jobs не считать PASS. На merged tree T05 целевые backend tests повторены: 24 passed, 1 warning. Локальные PG integration и synthetic staging/browser/cold-repeat timing — NOT_RUN.

T03 завершён после исправления omitted-day Sync на `clinic_today(db)` и отдельного code APPROVE пользователя; T04 — после отдельного явного deferral/merge authorization пользователя. Для T05 пользователь делегировал выбор между deferral и staging до merge. Принят отдельный deferral #3543: command-local settings без schema/API/ownership/admission-policy изменений, целевые regressions и применимые CI PASS; isolated synthetic staging остановлен. Это техническое решение агента по явному поручению пользователя, а не выдуманный GitHub approval от автора. Полные поля deferral и оставшееся покрытие — DECISIONS/EVIDENCE.

**Сейчас:** T06.2 подтверждённо слит в `b804a71a`; точные merge и CI сведения находятся в `EVIDENCE.md#t06.2-merge-checkpoint`. T07 runtime edits и локальная проверка завершены в отдельном worktree, но ещё не закоммичены. Свежий `origin/main` — `3a776133` после CI-only PR #3555; перед PR требуется rebase в этом worktree и повтор целевых проверок. Mandatory gate после одного разрешённого retry выдал `narrow_override` только для `_operations.py`; source inventory и точный ручной allowlist основаны на карточке T07 утверждённого пользователем плана. `gate_misroute=false`, `override_used=true`, `known_root_cause_file=backend/app/services/queue_svc/_operations.py`. T07 сохраняет v1 flag default-off; staging/PG runtime proof не выполнено.

## 4. Правила исполнения и постоянная память

### Вход в каждую сессию

1. Прочитать RESUME, этот план, PROGRESS, DECISIONS и последние evidence текущего этапа.
2. Проверить последнюю авторизацию пользователя; пауза сохраняется после compaction и смены агента.
3. Сверить worktree, branch, HEAD, diff, PR state/head/review/checks. При расхождении сначала восстановить checkpoint; не повторять выполненное.
4. Для нового PR получить свежий `origin/main`; работать в собственном worktree с `codex/aqs-Txx-<topic>`. Если текущий PR уже открыт, сначала продолжить его цикл; не создавать дубликат.
5. Перед первым edit записать execution mode, причину, risky domain, canonical anchors, reference-only, first-touch allowlist, denied paths, baseline, проверки и первый stop condition.

Все пути карточек ниже относительны корню **собственного worktree**. Исходные anchors проверены чтением на историческом `ae696ad1`; T05 факты сверены на merged tree `fd53206f`. Перед каждым этапом перепроверять на свежем main: это anchors, а не разрешение менять весь каталог. Новые policy/read DTO файлы помечены как проектируемые; точный путь записать до первого edit.

### PR-цикл и статусы

Цикл: baseline → узкий patch → целевые проверки → `git diff --check` → evidence → PR → исправление красных checks в том же PR → проверка актуального HEAD/review → допустимый merge → merge SHA → синхронизация базы → следующий этап.

| Статус | Что доказано |
|---|---|
| PLANNED | Работа не начата; anchors и критерии есть в карточке. |
| IN_PROGRESS | Baseline и boundaries записаны; изменение выполняется. |
| VALIDATED | Обязательные локальные проверки с SHA/evidence выполнены. Это не merge. |
| PR_OPEN | PR открыт; актуальные CI/review/ограничения записаны отдельно. |
| MERGED | GitHub подтверждает merge и точный merge SHA. |
| BLOCKED | Конкретный блокер, затронутые зависимости и путь разблокировки записаны. |

Пользовательская пауза — отдельное execution permission, не BLOCKED всех задач. `NOT_RUN` не равен FAIL или PASS. Обязательную проверку нельзя закрыть молча; допустимый PR-level deferral фиксирует область/причину/подтверждение, но не заменяет обязательный PG proof или pre-deploy runbook.

Каждый Txx — небольшой PR. При большом blast radius использовать Txx.1/Txx.2 с отдельными PR; родительский этап закрыть после всех подэтапов. Следующий PR-цикл не начинать при красном, неслитом или неразрешённом текущем PR. Доменная независимость не разрешает обход порядка. Изменение порядка при BLOCKED — явный checkpoint с причиной после закрытия текущего цикла, сохраняя зависимости.

Главный checkout `C:\final` — production surface. Не переключать ветки, не rebase, не хранить scratch, не запускать production из worktree. Не затирать чужой diff. Не удалять worktree, пока локальные документы/изменения не сохранены.

### Execution modes

- Узкие UI/read-only API для GPT-6: по актуальному AGENTS, обычно `advisory_gate`; вручную определить безопасный срез.
- Схема, квота, допустимость записи, публикация и queue commands: обязательный `gate`/`gate_known_root_cause`, `ai/langgraph/scripts/run_agent_gate.ps1` **из worktree**.
- DB/Alembic всегда mandatory gate; confirmed root → `--known-root-cause`; misroute исправлять по AGENTS, не обходить без основания.
- Документальное обновление 1.2: `direct_execute`, только план/журналы; нового runtime gate не требуется. Повтор T05 tests на merged tree записан отдельно от проверок docs-only diff.

### Checkpoint и evidence

PROGRESS — краткая актуальная точка продолжения. DECISIONS разделяет решения пользователя, canonical contract и технический выбор. EVIDENCE — append-only история; ранний FAIL не стирать после исправления.

После значимой проверки, перед завершением, compaction или передачей записать:

```text
Task/subtask; plan version/path; authorization/pause;
worktree/branch/base/actual HEAD; staged/unstaged paths;
canonical anchors; allowed/denied paths; mode/gate;
original failure/baseline; commands; PASS/FAIL/NOT_RUN and tested SHA;
CI run/PR/review state; scope check; limitation/blocker;
next exact action; checks to rerun after next change.
```

Для aif-implement всегда явный `@<absolute plan path>`: branch stem может обнаружить другой план. RESUME содержит условный будущий запуск. Не дублировать canonical plan ради имени ветки и не менять shared skills/config.

## 5. Порядок и зависимости

Стандартный порядок — T00 → T01 → … → T18, один закрытый PR-цикл за раз.

| Этап | Зависимости | Результат |
|---|---|---|
| T00 | нет | Документы, baseline, inventory |
| T01 / T02 / T03 / T04 / T05 / T10 | T00 | Узкие исправления соответствующего слоя |
| T06 | T00, T05 | Legacy-safe schema/creation snapshot |
| T07 | T05, T06 | Единое окно v1 |
| T08 | T06, T07 | Атомарная квота, покрытие writers |
| T09 | T03 | Безопасная смена сегодняшнего кабинета |
| T11 | T04, T10 | Ручная активность/effective parent policy |
| T12 | T10, T11 | Hidden-by-default/явная публикация |
| T13 | T03, T11, T12 | Canonical Admin read contract |
| T14 | T13 | UI на backend facts |
| T15 | T14 | Контекст настройки в URL |
| T16 | T09, T14, T15 | Навигация/совместимые входы |
| T17 | T10, T11, T12, T15 | Точные bulk/CSV результаты |
| T18 | T01–T17 | Полная синтетическая приёмка |

### Commit Plan

Каждый PR содержит code/test/docs checkpoints; разные Txx в один commit не объединять. Подэтапы T06/T08/T09/T13 — ниже. После T04–T05, T06–T08, T09–T12, T13–T16 и T17–T18 сверить сквозные dependencies/evidence; это не разрешение на rollout.

## 6. Карточки этапов

### T00. Документ и исходное состояние — MERGED

**Зависимости:** нет. **PR:** #3536. **Область:** документы плана.

Сохранены baseline, решения, реестр и admission-writer inventory. Staging был остановлен, disposable PG не проверялся; production data/config не запрашивались. Inventory/ограничения — EVIDENCE/T00. Это исторический этап, повторно не начинать.

При возобновлении проверить среду для текущего этапа; старая недоступность не доказывает сегодняшнее состояние. Synthetic fixtures: standalone/dangling/conflicting parent, mixed public profile, future legacy queue, inactive row той же identity.

### T01. Форма профиля — MERGED

**Зависимости:** T00. **PR:** #3537.
**Anchors:** `frontend/src/components/admin/QueueProfilesManager.tsx`, `queueProfileColors.ts`, `admin.css`; `frontend/src/components/admin/__tests__/QueueProfilesManager.interactions.test.tsx`.

Выполнены Select value, Dialog, keyboard/focus, buttons/labels и hex presets. Business semantics не менялись. Сохранить regressions при T17; не возвращать overlay/event-object обработку. Локальные/CI results — EVIDENCE/T01. Live QA/cold-repeat timing остаются сценариями T18.

### T02. Загрузка и черновик настроек — MERGED

**Зависимости:** T00. **PR:** #3538.
**Anchors:** `frontend/src/components/admin/QueueSettings.tsx`, `__tests__/QueueSettings.effective.test.tsx`; `frontend/src/stores/auth.ts` и focused tests.

Выполнены truthful loading/error/saving, save после successful GET, stale response guard, persisted draft base/owner metadata, logout isolation, dirty status при вводе во время save, defensive storage; удалены fake QR test/dev mode/диапазоны. Review fixes/CI записаны. Tier 2 deferral применялся к этому frontend-only PR; отложенные tests не стали PASS.

Сохранить draft guards при T07/T14. Blank max_per_day пока не команда удаления override: backend не имеет explicit unset semantics. Не превращать blank в zero/inherited fallback. При необходимости отдельный unset контракт согласовать вне текущего среза.

### T03. Согласованное чтение кабинетов — MERGED

**Зависимости:** T00. **PR:** #3540. **Режим:** advisory_gate, read-only API/UI.
**Anchors:** `backend/app/api/v1/endpoints/queue_cabinet_management.py`; `services/queue_cabinet_management_api_service.py`; `repositories/queue_cabinet_management_api_repository.py`; `repositories/queue_read_repository.py`; `services/queue_domain_service.py`; `frontend/src/components/admin/QueueCabinetManagement.tsx`.
**Tests:** `backend/tests/unit/test_queue_cabinet_management_api_service.py`; `backend/tests/integration/test_admin_linkage_cleanup.py`; focused cabinet frontend test/generated API parity.

Реализованы clinic-local day при omitted GET, typed owner/default/day cabinet, согласованные фильтры/счётчики, informational snapshot/default difference, retry/stale response protection. Review выявил cross-day Sync при omitted day; follow-up `e18d2e2c` исправил backend default на тот же `clinic_today(db)` и добавил divergent clinic/host date regression. Пользователь подтвердил закрытие P1 и code APPROVE. Schema/admission/ownership не менялись.

**Закрытие:** PR #3540 MERGED в `1e781da72bd927926b538b139a6c251cd09848b5`. Tier 2 принят отдельно, отложенные staging specs/timing остаются NOT_RUN. История CI/OpenAPI исправлений и точные проверки — EVIDENCE/T03. Не возобновлять старый PR_OPEN checklist и не повторять уже исправленный Sync defect как новую задачу T09.

### T04. Правдивый пустой каталог профилей — MERGED

**Зависимости:** T00; следующий цикл после T03. **Режим:** advisory_gate; eligibility writer → stop/new gate slice.
**First-touch candidates:** `backend/app/api/v1/endpoints/registrar_integration/_queue_profiles.py`: `get_queue_profiles`, `get_queue_profiles_public`; `frontend/src/components/navigation/Tabs.tsx`: `loadQueueProfiles`; focused GET/Tabs tests.
**Reference-only:** `backend/app/models/queue_profile.py:INITIAL_QUEUE_PROFILES`, явный seed/provisioning.

**Закрытие:** #3541 MERGED в `ecc14b05411c7e7b54efca2966416cd6a69df37c`. Empty admin/public catalog и DB failure разделены; Tabs не восстанавливает hardcoded profiles и сохраняет последний успешный список при failed refresh. Пользователь явно принял отдельный Tier 2 deferral и разрешил merge на `b59fff8a`. Regression/CI/evidence — журнал T04; staging не стал PASS. Ниже сохранены исходные требования, а не новые невыполненные этапы.

1. Зафиксировать backend empty/exception → standard profiles и frontend rejected GET → fallback.
2. Пустой настроенный каталог возвращает successful empty list. Ошибка — API error по existing exception contract, без success:true/defaults.
3. Удалить runtime fallback Tabs; truthful empty/error/retry. GET не создаёт профили, seed constants сохраняются.
4. `Tabs.a11y.test.tsx`/`Tabs.focusRefresh.test.tsx` сейчас содержат fallback assumptions: заменить fixtures successful API catalog, сохранить a11y/focus проверки.

**Validation:** empty table/all inactive/all hidden/DB failure/retry/reload после disable-all; focused GET/Vitest, type-check, scoped lint, parity при DTO change.
**Приёмка:** reload не восстанавливает standard tabs; error не маскируется empty.
**Denied/stop:** defaults creation, lifecycle/publication/parent change, широкий Tabs refactor.
**Evidence/logs:** до/после safe responses и tests/SHA; safe ERROR чтения, без per-profile INFO.

### T05. Fresh defaults без постоянного кэша — MERGED

**Зависимости:** T00. **Режим:** gate_known_root_cause: settings влияют на admission; root `_core.py`.
**Anchors:** `backend/app/services/queue_svc/_core.py:CoreMixin._load_queue_settings` и command settings context; settings-consuming commands в `queue_svc/_operations.py`; `backend/app/crud/queue_resource_routing.py:effective_day_start_number`; `backend/app/crud/clinic.py:get_queue_settings`.
**Reference-only:** `services/queue_service.py` singleton shim, `queue_svc/_helpers.py`, composed service `queue_svc/__init__.py`. Дублирующие `_cached_settings` initializers удалены в T05; не считать их текущим API.

**Закрытие:** #3543 MERGED в `fd53206f03b0361de6fc345f53b2bacf4195845c`, 2026-10-01T16:24:40+05:00. ContextVar snapshot keyed by service + DB session: nested commands переиспользуют его, следующая команда перечитывает defaults, finally освобождает контекст. Creation передаёт тот же settings mapping в расчёт start number; существующий snapshot сохраняется. Runtime commit `47276d17`, reviewed PR HEAD `c04f4102`; merged tree совпадает с ним. На merge повторён focused suite: 24 passed, 1 warning. Кандидаты PG/effective-report ниже не отмечать PASS без отдельного запуска. Локальные PG integration и synthetic staging/browser NOT_RUN; ограниченный deferral принят агентом по отдельному поручению пользователя и закреплён в DECISIONS/EVIDENCE.

1. Same service instance: A → сохранение B → новая команда ошибочно использует A; regression до patch.
2. Fresh defaults в начале новой команды, coherent snapshot внутри неё. Mutable «current command defaults» в singleton не вводить: параллельные команды не перезаписывают snapshots друг друга.
3. Проверить обе `_cached_settings` и command consumers; wrappers менять только по evidence, restart/process-only invalidation не решение.
4. Existing DailyQueue сохраняет свои snapshot values; не подключать неработающие department defaults.

**Validation:** `test_effective_queue_settings_report.py`, `test_rq13b_daily_queue_snapshot_pg.py`, `test_queue_time_window.py`; same-instance/concurrent-command regression.
**Приёмка:** следующая команда видит B без restart, старая очередь сохраняет A.
**Stop:** snapshot/ownership change, premature window/quota semantics.
**Evidence/logs:** command boundary/snapshot passing; safe ERROR load failure, без per-read INFO.

### T06. Сохраняемая политика новых дневных очередей

**Зависимости:** T00, T05. **Режим:** mandatory gate, DB/Alembic.
**Anchors:** `backend/app/models/online_queue.py:DailyQueue`; `backend/app/crud/queue_resource_routing.py:effective_day_start_number`, `resource_queue_defaults`, registry locks.
**Reference-only revisions:** `backend/alembic/versions/0063_queue_resource_contract.py`, `0067_daily_queue_start_number_snapshot.py`; applied revisions не менять.

Срезы: **T06.1** model/new revision/legacy-safe schema; **T06.2** shared calculation/runtime constructors. Создание v1 выключено до всех обязательных proof.

1. `policy_version`: legacy/daily_online_issuances_v1; `online_issued_count`: integer CHECK >=0. Existing rows legacy + technical 0, без source backfill.
2. Сохранить owner XOR/identity constraints; revision от единственного актуального head, non-destructive upgrade.
3. Common backend creation calculator — **новый проектируемый module**; existing queue_policy.py нет. Path/ownership записать до edit; новая business entity не нужна.
4. Все активные runtime DailyQueue constructors получают version/counter и snapshot parameters через общий backend calculation: `queue_svc/_operations.py`, `crud/online_queue.py`, `graphql/mutations.py`, `repositories/queue_api_repository.py`, `queue_limits_repository.py`, `visit_confirmation_repository.py`. Классифицировать seed/`force_majeure_service.py`/`migration_service.py` live/offline/legacy; доказать их безопасную совместимость, не переписывать вслепую.
5. `QUEUE_POLICY_V2_CREATION_ENABLED=false` default: только new rows. Flag off не отменяет правила existing v1. Version/count недоступны ordinary admin PATCH.
6. Старые/future queues автоматически не переводить; start_number=1 inheritance через existing helper.

**Validation:** heads/history/single head, disposable PG upgrade/data/ownership, negative count rejected, v1 zero/snapshot, constructor parity общего calculation, old-writer expanded-schema compatibility до активации, flag new rows only. SQLite PG не заменяет.
**Stop:** multi-head/destructive upgrade/no required PG/unknown constructor ownership.
**Evidence/logs:** revision chain, safe synthetic aggregates, constructor classification, INFO существенного создания без patient payload.

### T07. Единое окно онлайн-записи

**Зависимости:** T05, T06. **Режим:** mandatory gate.
**Anchors:** `queue_svc/_operations.py:check_queue_time_window`, `_unbookable_doctor_ids`, `_pick_least_loaded_doctor`; `qr_queue/_queue_ops.py:_check_online_time_restrictions`; `qr_queue/_sessions.py`; `graphql/mutations.py:_join_queue_impl`; `services/queue_auto_close.py`; `crud/clinic.py` settings/effective report.

1. V1 `[start,end)` по clinic timezone: existing queue snapshot; no queue → fresh command defaults и то же creation calculation.
2. Убрать fixed 07:00/disabled end check/расхождение queue_end_hour-auto_close_time. Metadata/selection/join используют одну policy.
3. Canonical HH:MM validation/start<end; overnight interval отклонить понятно.
4. Manual earlier close сохраняется; join отказывает независимо от scheduler. Existing patient service не закрывается.
5. Future-date contract сохранить; legacy явно старой policy, без hidden conversion. После integration убрать из T02 только устаревший cutoff hint; draft guards сохранить.

**Validation:** before/exact start, before/exact end, manual earlier/no scheduler, UTC-clinic mismatch, no row/existing snapshot, defaults update, invalid start/end, legacy/future-date parity. `test_queue_time_window.py`, `test_effective_queue_settings_report.py`, snapshot/QR/token/GraphQL suites. `auto_close_time_is_display_only` менять вместе с v1 contract; legacy report остаётся truthful.
**Stop:** overnight/clinical lifecycle/silent legacy conversion.
**Evidence/logs:** совпадение availability/join для каждого boundary; safe WARN refusal/ERROR failure, anonymous diagnostics не расширять.

**Подтверждённые активные точки интеграции для T07:** основной `QueueBusinessService.join_queue_with_token` и `_unbookable_doctor_ids`; прямой GraphQL `joinQueue`; QR session precheck в `qr_queue/_queue_ops.py`; публичный `/online-queue/status` через `crud/online_queue.check_queue_availability`; `QueueAutoCloseService` как отдельный переход к обслуживанию. `crud/online_queue.join_online_queue` находится в transitional CRUD и не имеет найденного смонтированного caller — не считать его активным admission writer без новых source evidence. Для существующего `legacy` сохраняются текущие правила допуска без нового end cutoff; `daily_online_issuances_v1` использует frozen start/end и clinic timezone. На несуществующую очередь availability применяет те же defaults/policy flag, которые использует её последующее создание. Будущие даты сохраняют существующее правило: временное окно текущего дня не применяется к ним. Это техническое толкование runtime и принятого плана, не новая продуктовая договорённость.

Для clinic-wide QR overview при смешанных legacy/v1 очередях нельзя использовать политику случайной первой строки как общий cutoff: обзор доступен, когда хотя бы одна активная и ещё не открытая очередь допускает запись по времени; `opened_at` закрывает admission только этой очереди. Конкретная выбранная очередь повторно проверяется каноническим join. Если все неоткрытые цели закрыты по времени, read result сообщает ближайшее соответствующее открытие/закрытие v1; если открыты все цели, сохраняется ответ `closed_reception_opened`. Это техническая детализация адаптера; она не меняет отдельные цели записи и сохраняет старое поведение legacy.

Для clinic-wide QR overview при смешанных legacy/v1 очередях нельзя использовать политику случайной первой строки как общий cutoff: обзор доступен, когда хотя бы одна активная и ещё не открытая очередь допускает запись по времени; `opened_at` закрывает admission только этой очереди. Конкретная выбранная очередь повторно проверяется каноническим join. Если все неоткрытые цели закрыты по времени, read result сообщает ближайшее соответствующее открытие/закрытие v1; если открыты все цели, сохраняется ответ `closed_reception_opened`. Это техническая детализация адаптера; она не меняет отдельные цели записи и сохраняет старое поведение legacy.

### T08. Дневная квота успешных онлайн-выдач

**Зависимости:** T06, T07. **Режим:** mandatory gate, locking/admission.
**Anchors:** `services/queue_domain_service.py:allocate_ticket`; `queue_svc/_operations.py:join_queue_with_token`, `check_queue_limits`, `get_next_queue_number`, batch prelocks; `services/queue_claim_service.py`; `crud/queue_resource_routing.py` claim/registry locks.

Срезы: **T08.1a** canonical token quota; **T08.1b** v1 identity/recreation guard; **T08.2a** GraphQL direct writer; **T08.2b** remaining active admission adapters after source proof; **T08.2c** availability/report parity; **T08.3** PG concurrency/replay/partial proof. V1 не включать при неполном покрытии; facade-only change GraphQL не покрывает. Current T08.2a must keep its first PR limited to GraphQL and its focused tests. Telegram remains inventory-only unless a live issuance path is proven; the current source audit says its callback fails before a queue write.

#### T08.2c — Availability and report parity

**Scope:** read-only reporting across `GET /online-queue/status`, concrete QR availability/info, Admin `GET /queue-status`, and specialty aggregate `GET /queue-limits`; corresponding Pydantic/OpenAPI/generated TypeScript contracts and focused tests. Do not change admission writers, queue identity, schemas, or the creation flag.

**Contract:** V1 uses the saved daily-queue cap and `online_issued_count`; remaining is `max(0, cap - issued)`. `queue_length` separately counts waiting/called entries, regardless of source. Legacy issued/remaining are null because the migrated zero does not prove history; the legacy active-entry enforcement semantics remain. A clinic-wide QR overview that combines owners or policies must not expose one queue's cap/count/remaining. Specialty aggregates expose `policy_version=mixed` and null issuance/remaining when a legacy member makes the sum unknown. Preserve historical aggregate `current_usage`; add active `queue_length` separately. Rowless reports use the owner defaults that the next queue constructor would consume.

**Acceptance:** response values agree with the canonical quota/window owner; zero cap remains zero for v1; canceled/completed legacy rows do not become a fabricated issued count; mixed overview/aggregate values are explicitly unknown; OpenAPI and generated types match DTOs; focused unit/OpenAPI and resource integration tests pass. PostgreSQL concurrency remains T08.3, and staging is not a prerequisite claimed by this read-only slice.

V1 transaction contract:

1. Existing replay/claim проверить до новой admission; replay работает и когда новых мест нет.
2. Existing sorted claim/tag locks, затем daily queue lock до quota check; fairness/number allocation сохраняются.
3. Window/effective eligibility/count<max; zero не подменяется `or DEFAULT`.
4. Independent online entry + counter + replay result в одной existing transaction. Caller-owned flush/commit сохранять, hidden independent commit не вводить.
5. Rollback/replay не increment; cancellation/served/no-show/deletion/transfer не decrement. Staff derivative source=online не increment. Partial batch — только committed successes.

Таблица coverage обязательна: mounted/active?, admission function, transaction owner, locks, policy/counter, replay proof, test/SHA.

| Путь | Anchor и proof |
|---|---|
| QR session | `api/v1/endpoints/qr_queue/_join.py`, `services/qr_queue/_sessions.py`; start/probe не issuance, final commit/replay trace |
| Permanent address | `qr_queue/_directions.py` → session; address/TTL/access сохранить |
| Legacy token | `api/v1/endpoints/queue.py`; direct token join |
| Compatibility online | `api/v1/endpoints/online_queue_new.py` → façade; real join/boundary |
| GraphQL | `graphql/mutations.py:_join_queue_impl` directly inserts/commits; explicit integration |
| Telegram candidate | `api/v1/endpoints/telegram_bot.py` → `services/telegram/bot.py:_handle_queue_callback`; calls missing join_queue, hardcodes specialist/window. Active/reachable contract сначала доказать |
| Staff/derivatives | registrar wizard/_today_queues, batch patient/queue, visit confirmation, transfer/clone; source не является proof online issuance |

Identity guard: искать active/inactive same doctor/day/tag или resource/day. Partial active uniqueness недостаточна. Не создавать zero-count replacement; ordinary commands не reset counter/identity/delete used v1; conflicting queues не merge автоматически.

T08.1b implementation boundary: v1 identity check belongs on the shared `daily_queue_creation_snapshot` path so every active runtime constructor using that policy supplies the queue date and typed owner. The known call sites include `queue_svc/_operations.py`, `crud/online_queue.py`, GraphQL, queue API, queue limits, visit confirmation and force-majeure creation. Legacy queue creation must keep its prior behavior. Migration import/restore must preserve stored policy/count; dev seeding is not an online runtime writer. Existing Admin retention cleanup is bounded to rows older than a cutoff of at least one day; past-date admission is rejected by T07, so it cannot delete today's/future identity or reopen an eligible quota. Before closing T08.1b, source-scan ordinary mutation/delete paths for `policy_version`, `online_issued_count`, owner identity and `DailyQueue` deletion. SQLite tests do not replace T08.3 PostgreSQL concurrency proof.

**Validation:** independent PG sessions last-slot → ровно одна issuance; response-loss replay/rollback; statuses/deletion; desk/source-online clone/transfer; partial result; inactive recreate; tags; identical doctor/resource numeric IDs. Existing allocator characterization/concurrency, claim/QR/GraphQL boundary/integration suites; meaningful new PG race proof, не mocks вместо locks.
**Reporting:** queue length/issued/remaining/version раздельно; v1 remaining=max(0,max-count); legacy count unknown.
**Stop:** active writer bypass/reset/no required PG/Telegram требует другого product contract. Допустим bounded adapter slice, не общий bot rewrite.
**Evidence/logs:** writer coverage/transaction proof; safe WARN quota/identity, ERROR transaction, без tokens/patients.

### T08.3 execution split — PostgreSQL proof checkpoints

T08.3 spans several independent admission transaction owners. To keep each PR bounded and preserve a clear resume point, implement and merge these sub-tasks in order. Every sub-task uses synthetic rows and independent real PostgreSQL sessions; SQLite is not lock evidence. The creation flag remains default-off throughout.

#### T08.3.1 — Legacy queue-token admission transaction

**Status:** MERGED — [PR #3599](https://github.com/drsapaev/final/pull/3599), merge commit `a452c54e5851611476c1b2ac3e3298aeff467eca`.
**Owner:** `backend/tests/integration/test_daily_queue_lock_parity_pg.py`; runtime is read-only.
**Required proof:** independent token admissions contend for the last v1 daily-queue slot and produce exactly one new online entry/counter increment; a repeated exact-token identity returns the existing ticket with no second increment after the cap is full; rollback removes the uncommitted entry and restores the v1 counter and token usage together.
**Stop:** runtime defect, missing shared quota boundary, ambiguous token/identity contract, or unavailable disposable PostgreSQL. Do not expand into runtime edits under this slice.
**Evidence:** focused PostgreSQL module 5 passed; the two added tests separately proved one issuance at the last slot, no second counter increment on exact-token replay at a full cap, and rollback of entry/counter/token usage. Existing queue policy, GraphQL claim coordinator and online-window unit modules passed 65 tests. First local PG attempt was interrupted by a normal WSL Docker daemon shutdown; stable rerun completed all five tests. See `admin-queue-simplification/EVIDENCE.md` for exact commands/environment and limitations.

#### T08.3.2 — QR join-session transaction and partial batches

**Status:** MERGED — [PR #3600](https://github.com/drsapaev/final/pull/3600), merge commit `b3bd5272389da88513cc1ac23985b390489554f9`. Its post-merge P2 follow-up is [PR #3607](https://github.com/drsapaev/final/pull/3607); local validation passed and exact-head checks are pending.
**Owner:** `backend/tests/integration/test_qr_family_phone_identity.py` for synthetic disposable PostgreSQL transaction tests; `backend/app/services/qr_queue/_sessions.py` is canonical runtime reference and remains read-only unless a separate gate authorizes a fix.
**Required proof:** lost-response replay returns the saved response without a second issuance; single/multiple queue writes and replay snapshot share the existing outer transaction; a permitted partial result commits only successful elements and accurately reports rejected elements/counter totals. Preserve the existing partial-result contract.
**Execution boundary:** test/evidence-only. The merged PR added real PostgreSQL tests for single/multi transaction rollback, response replay and partial result. A post-merge P2 found four new tests relied on the live clinic time with a `23:59` cutoff. Follow-up adds a fixed midday clock and explicit matching queue day to those tests; runtime remains read-only. See `admin-queue-simplification/EVIDENCE.md#t0832-clock-follow-up`.
**Local evidence:** original focused PostgreSQL module passed 11 tests. After the deterministic-clock fix the complete module again passed **11 passed, 0 skipped** on disposable PostgreSQL 16; Ruff, Black check, `py_compile` and `git diff --check` passed. The earlier run that returned 11 skips after WSL idled is not counted. PR #3607 is open; its body quality gate passed; exact PR HEAD `d4d1524aa96f7260825b6f0caf1b9cb724044490` had 10 successful checks, 4 skipped, 0 failed. The current evidence-only checkpoint will trigger checks on a new HEAD.

#### T08.3.3 — Direct GraphQL and remaining reachable writer parity

**Status:** PLANNED; begin after the T08.3.2 post-merge P2 follow-up PR cycle is merged.
**Owner candidates:** `backend/app/graphql/mutations.py` plus a focused real-PG test owner and the T08.3 writer coverage table.
**Required proof:** direct GraphQL last-slot behavior and a source-backed inventory of compatibility/API adapters; status changes, desk derivatives, transfers, deletion and replay never decrease/re-spend the independent issuance counter. Include only adapters proven mounted/reachable. If the legacy `/queue` writer lacks a quota boundary, stop and create a separately gated runtime sub-task.

### T09. Безопасная смена сегодняшнего кабинета

**Зависимости:** T03. **Режим:** mandatory gate, command/audit.
**Anchors:** `services/queue_cabinet_management_api_service.py`; `repositories/queue_cabinet_management_api_repository.py`; `api/v1/endpoints/queue_cabinet_management.py`; `frontend/src/components/admin/QueueCabinetManagement.tsx`; existing `models/audit.py:AuditLog`.
**Reference-only:** T03 read, `crud/clinic.py:update_doctor`, `services/audit_service.py`; resource default writer найти до allowlist.

Срезы: **T09.1** preview/DTO; **T09.2** locked apply/strict audit/replay; **T09.3** UI/containment legacy bulk/sync.

1. Разделить owner default save и explicit queue-ID clinic-today apply; history/future/defaults не затрагивать.
2. Read-only preview: typed owner/day/old-new/waiting count. Apply: expected old state/reason/stable command replay identity по project pattern; форму записать до edit.
3. Под locks повторить day/owner/cabinet/safety checks. Stale →409, no partial apply; called patient/active clinical execution блокируют перенос.
4. Change+mandatory audit атомарно. Existing log_audit_event independently commits/swallow errors; этот helper контракт не выполняет. Narrow strict audit insertion в existing table в command transaction; unrelated callers не переписывать.
5. Identical replay не duplicate change/audit. Legacy update/bulk/sync не обходят safeguards. Omitted-day Sync уже переведён на clinic_today в T03; проверить остальные writers и containment, не повторяя закрытый дефект.

**Validation:** today only/yesterday-future-defaults-numbers-status untouched; stale atomic409; audit-failure rollback; replay; resources/waiting count/called block/legacy bypass. Cabinet service/Admin linkage/resource tests + new PG commands/UI.
**Stop:** called/active transfer, audit cannot atomic, unknown write ownership.
**Evidence/logs:** actor/typed target/old-new/reason/request ID; INFO change/WARN refusal/ERROR failure; operator procedure default vs today.

### T10. Используемые связи профиля

**Зависимости:** T00. **Режим:** mandatory gate.
**Anchors:** `registrar_integration/_queue_profiles.py`: canonical tags/link counts/preview/update/delete; `models/queue_direction_public_address.py`.

1. Зафиксировать PUT bypass delete guard. Usage=services/queues/entries/active public address; helper адрес пока не учитывает.
2. Used profile: запрещены queue_tags/significant order/department_key change. Presentation/archive разрешены; порядок не потерять через сортировку.
3. Preview old/proposed config без mutations; PUT revalidate dependencies до первого setattr, stale preview не разрешение.
4. Mixed PUT с forbidden binding reject целиком; safe structured impact errors.

**Validation:** `backend/tests/integration/test_queue_profile_lifecycle.py`: tags/order/department, unused edit, presentation/archive, address-only usage, stale preview, atomic mixed reject, history/address preserved.
**Stop:** owner transfer/address rebind/unknown canonical alias equality.
**Evidence/logs:** field/usage impact, safe WARN refusal/INFO change/audit по existing command contract; lifecycle T11/T12 не менять здесь.

### T11. Ручная активность и родитель

**Зависимости:** T04, T10. **Режим:** mandatory gate.
**Anchors:** `admin_departments/_helpers.py:_department_linked_profiles`, `_sync_department_active_to_profiles`; `_crud.py` lifecycle writers; `queue_svc/_core.py` visibility; `qr_queue/_specialists.py`. Shared backend profile policy — проектируемый module.

1. is_active сохраняет manual intent; department off/on его не меняет. Preexisting false сохранить без угадывания.
2. Parent: explicit department_key/ documented own-key; обе разные→conflict; missing explicit→conflict; neither→standalone. OR-связь не доказательство корректности.
3. Effective availability backend; batch parent read/no N+1; reasons distinguish manual archive/parent off/dangling/conflict.
4. List/selection/direct join/old token/permanent address/batch resolution используют policy; existing patients serviceable. Consumers `_operations.py`, `_sessions.py`, `_tokens.py`, `_directions.py`; shims reference-only.

**Validation:** lifecycle single/bulk off-on, manual archive, all false preserved, standalone/dangling/conflict, query bound, off-parent direct/token/address refusal. Existing lifecycle, `test_qr_selection_join_visibility.py`, `test_qr_token_path_owner_eligibility.py`, `test_rq16d_public_direction_runtime.py`.
Old mutation tests менять с контрактом, history guards сохранять.
**Stop:** automatic repair/historical intent inference/unknown parent policy.
**Evidence/logs:** persisted vs effective before-after; WARN conflict/INFO department change; reads не пишут state/per-row logs.

### T12. Явная публикация и обзор

**Зависимости:** T10, T11. **Режим:** mandatory gate.
**Anchors:** `_queue_profiles.py` create/update; `admin_departments/_helpers.py:_ensure_department_integrations`; `models/queue_profile.py`; `_operations.py` direction resolve/join; `crud/queue_resource_routing.py` resource routing. Alias/tag vocabulary: `backend/app/core/specialties.py` (`expand_queue_tags`, `canonical_specialty`, `specialty_variants`); QR normalization/constants: `queue_svc/_core.py`/`_base.py`.

1. Manual/automatic new profiles show_on_qr_page=false, model/request defaults согласованы. Входящий POST show_on_qr_page=true от старого UI/CSV не создаёт опубликованный профиль: backend отклоняет либо явно откладывает намерение до отдельного publish action. Конкретный совместимый response contract закрепить до edit. Existing profiles mass-hide не делать.
2. Explicit publish через existing update, readiness/target checks внутри transaction; reactivation с saved publication intent revalidates.
3. Multiple doctors одной specialty и services одного однозначного owner допустимы. Mixed independent directions overview; booking через first resource не разрешать.
4. direction_resolves_to_bookable_surface сегодня принимает первый resource: boolean не готовая uniqueness policy. Existing backend aliases, не React duplicate.
5. Existing ambiguous public configs diagnostic/block new admissions включая token/address; addresses/bindings не reassign.

**Validation:** both hidden constructors/POST с incoming publication=true/publish/reactivation atomic refusals/same-direction doctors/mixed overview/token/address parity. Department create atomicity, QR visibility/rq16b-c-d/resource suites; old addresses unchanged.
**Stop:** требуется product target choice/rebind/owner merge.
**Evidence/logs:** saved intent vs effective availability, safe INFO publish-hide-archive/WARN refusal; no runtime repair.

### T13. Canonical Admin directions GET

**Зависимости:** T03, T11, T12. **Режим:** advisory_gate read-only после policy stages.
**Новый endpoint:** GET /api/v1/queue/admin/directions, Admin only. Endpoint/schema/service/repository ещё отсутствуют; exact paths выбрать после grounding.
**Existing references:** `api/v1/endpoints/qr_queue/_directions.py`; `_operations.py` primitives; `services/appointment_eligibility.py`; `crud/queue_resource_routing.py`; `repositories/queue_read_repository.py`; `services/queue_domain_service.py`.

Срезы при необходимости T13.1 DTO/contract, T13.2 bounded aggregation/OpenAPI. Не BFF-service и не новая business-policy внутри screen endpoint.

DTO: profile/settings; saved manual/publication intent; effective state/reasons; booking/overview mode; typed doctor/resource targets; public availability/address presence; allowed action kinds/entity refs без arbitrary URLs; unassigned tags/services/resources. Ordinary booking и automatic precreate feasibility раздельно; Service.doctor_id не обязателен multi-doctor направлению.

GET не создаёт queues/tokens/addresses/sessions/progress; DTO без PHI. Inactive resource с saved daily queue включается; active-only resolve_tag_resource недостаточен для истории.

**Validation:** Admin auth unchanged/zero writes/empty/conflicts/overview/disabled-hidden/same numeric typed IDs/inactive owner-saved queue/action consistency/bounded queries/OpenAPI required-nullable-enums. `backend/tests/test_openapi_contract.py`, new focused Admin suite, rq16b DTO reference.
**Stop:** data creation в GET/guess eligibility/auth redesign.
**Evidence/logs:** DTO/action command mapping and query bound; safe ERROR only, types existing generator, не manual edits.

### T14. Setup UI на backend facts

**Зависимости:** T13. **Режим:** advisory_gate, clinic UI skill.
**Anchors:** `frontend/src/components/admin/AdminSetupDirections.tsx`, `setupDirectionsReadiness.ts`, `PermanentDirectionQr.tsx`; existing `frontend/src/api/queueDirections.ts`.

1. Заменить local buildChecklist/alias/collectServiceAssignmentGaps/owner-axis decisions facts T13; frontend formats known states/actions.
2. Configuration/public entry/selected-day queues разделены; resource-only без «создать врача».
3. Core rows не ждут per-profile QR: сейчас loadCore waits после четырёх catalog calls; QR on expand/bounded/deduplicated.
4. QR error не скрывает table; stale core/QR не заменяют newest profile/day.
5. Admin GET в existing API module если граница подходит; не duplicate client, useful QR stale/dedup tests сохранить.

**Validation:** readiness/unknown/overview/conflict, rows before QR/error-retry/stale day-profile, no policy in React, type/lint/tests/synthetic cold-repeat waterfall. `setupDirectionsReadiness.test.ts`, `adminSetupDirections.textPin.test.tsx`, `permanentDirectionQr.test.tsx`, rq17.
**Stop:** facts недостаточны→T13 repair, не restore React policy.
**Evidence/logs:** request/content timing/DTO states; no raw payload, synthetic screenshots.

### T15. Восстанавливаемый контекст настройки

**Зависимости:** T14. **Режим:** advisory_gate; URL contract сначала plan/dossier.
**Anchors:** AdminSetupDirections; existing ServiceCatalog/UserManagement/UserModal/QueueResourceManager/QueueProfilesManager TSX.

1. Убрать unconditional Next/Finish; outstanding actions из T13, completion не local flags.
2. Profile/section/day в URL; view/step/axis/tag сейчас component state, existing typed return context не найден.
3. До edit DECISIONS: technical query keys/types/sections/entity kinds/internal destinations; arbitrary redirect URL не принимать, auth/RBAC не менять.
4. Catalog/users переход с typed return context; save/return rereads facts; cancel/back не фиксирует fake completion.
5. Reuse UserModal doctor onboarding; editor reuse постепенно, без второго wizard/refactor unrelated.

**Validation:** save-return/cancel/reload/back-forward/deep link/unknown context/external changes/resource-only; UserModal onboarding/setup/rq17 plus focused URL tests.
**Stop:** new ownership/security decision/second onboarding/progress table.
**Evidence/logs:** URL/action mapping, safe error states; no noisy query/token logs; operator resume flow.

### T16. Навигация и совместимые входы

**Зависимости:** T09, T14, T15. **Режим:** plan/dossier перед advisory execute, routing SSOT.
**Anchors:** `frontend/src/routing/routeRegistry.ts`, `routeSelectors.ts`, `routeDocsSnapshot.ts`; `frontend/src/components/admin/AdminServices.tsx`; page adapters/Sidebar i18n.

1. Setup «Направления и очереди», settings «Общие правила очереди».
2. Cabinet URL → today queues; servicesTab=queue-profiles → profiles unified context; catalog сохраняется, whole /admin/services redirect запрещён.
3. Query/local state/back-forward согласовать: сейчас initial-only query/unknown nonempty accepted. Unknown→safe start.
4. Admin rights/nav highlight/function access сохранить; unrelated role routes не менять.

**Validation:** routeContract/routeOwnershipEnforcement/Sidebar.navI18n/rbacRouteParity tests; query changes/history; admin-navigation; four original URLs/catalog/unknown query.
**Stop:** auth/route ownership change/mass alias cleanup.
**Evidence/logs:** verified URL mapping/nav contract; no raw query logs; docs snapshot existing pattern/operator links.

### T17. Массовые операции и CSV

**Зависимости:** T10, T11, T12, T15. **Режим:** advisory existing-command UI; new write contract→separate mandatory slice.
**Anchors:** QueueProfilesManager.tsx/queueProfilesCsv.ts; QueueProfilesManager.csv.test.tsx/queueProfilesCsv.test.ts/interactions; backend _queue_profiles reference-only.

1. Bulk sequential loop сегодня aborts first error/no reload; exact row success/rejected/not-started + safe reason.
2. Partial outcome→reread actual state даже при error. Retry failed/not-started only после revalidation.
3. Impact preview/structured errors T10–T12; stale preview не обещает success.
4. Parser/RFC4180/round-trip уже реализованы: не переписывать. Department/optional/export поддерживаемые поля сохраняются.
5. New CSV POST always hidden; publication intent отдельный pending action после readiness, без auto-publish/молчаливой потери намерения.

**Validation:** success-fail-not-started/partial import/network-loss/reload fail/retry remaining/used conflicts/publication/optional/round-trip; preserve T01 Dialog/keyboard.
**Stop:** нужен bulk transaction/new backend command/missing structured errors→bounded contract slice.
**Evidence/logs:** row outcomes/retry set; safe row codes/IDs, CSV content не логировать.

### T18. Полная синтетическая приёмка

**Зависимости:** T01–T17 и подэтапы. **Режим:** QA/evidence; выявленный code defect→bounded fix в соответствующем PR.
**Anchors:** `frontend/e2e/rq17-setup-directions-live.spec.ts`, rq18 permanent-QR, Tier2 specs; `frontend/playwright.config.ts`; runbooks LOCAL_STAGING_ACCEPTANCE/AGENT_SESSION_WORKTREES/SCREEN_LATENCY_REGRESSION/STAGING_VALIDATION.

До запуска deployed commit/frontend-API-DB synthetic isolation proof. Config hardcodes localhost5173, panel-qa-admin-live собственный baseURL; override проверять включая per-spec URLs. Не reuse сервер, направленный на production18000. REAL_API rq17/rq18 создают данные, production запрещён.

Каждый сценарий отдельной строкой PASS/FAIL/NOT_RUN + SHA/artifact:

1. Новое направление с несколькими врачами одной specialty/typed targets.
2. Направление без врача/resource-only без лишнего onboarding.
3. Исправление incomplete/conflicting config/truthful next actions.
4. Hidden→explicit publish→hide/archive; address unchanged.
5. Department off/on/manual archive/old token-direct join refusal.
6. Defaults save-read-consume без restart/current snapshot unchanged.
7. Cabinet preview/apply/stale/audit rollback/called-clinical block.
8. Concurrent last slot/exactly one/consistent remaining.
9. Lost response/replay/no double count/rollback-partial conservation.
10. Four old URLs/catalog/typed return/reload/back-forward.

Keyboard-only/focus/forms/errors/retry/empty/locales; viewport375/768/1280/1920. Cold actual rows/repeat same conditions: role/browser/network/data/commit/asset-API-backend-DB waterfall. Spinner/first paint не rows; runbook baseline не универсальный SLA.

Artifacts established output/playwright/test-results по runbook; auth-state/tokens/full payload не коммитить. Safe paths/aggregates в evidence.
**Приёмка:** доказательства конкретного deploy commit, без скрытых NOT_RUN; separate ten-point staging validation ниже.
**Stop:** no required env/check/real patient origin/contract regression. QA не отключает PII masking.

## 7. Контракты и обязательные проверки

| Контракт | Изменение |
|---|---|
| Profiles read | Empty/error; effective state/reasons после T11 |
| Profiles update | Used-binding guard/transactional publish-reactivate revalidation |
| Cabinet read | Typed owner/day snapshot-default/same filter-count facts |
| Cabinet commands | Explicit IDs/expected state/reason/atomic audit/replay |
| Directions Admin GET | Typed read-only/actions/entity refs/Admin only/no PHI |
| Availability/report | Length/issued/remaining/version; legacy unknown |

OpenAPI required/nullable/enums/typed owner. Anonymous QR disclosure сохраняется; safe Admin code/details объясняют correction. DTO changes→generator/freshness/type parity; serializer matching scripts, не ручное форматирование.

| Область | Обязательный proof |
|---|---|
| Forms/settings | Select/keyboard/focus/presets; GET fail no PUT; stale draft owner/base; dirty during save |
| Defaults/snapshots | Same instance/no restart; concurrent command coherence; old/future snapshot |
| Time | Four [start,end) boundaries/manual/no scheduler/timezone/future dates |
| Quota/identity | PG race/replay/rollback/status-delete/clone-transfer/partial/inactive recreate/typed IDs |
| Profiles | Disabled/parent off-on/manual/dangling-conflict-standalone/used tags-order-address |
| Publish | Hidden constructors/publish-reactivate/mixed overview/token-address/same-direction doctors |
| Cabinets | Filter-history/stale409/audit rollback/resource/called block |
| Routing/CSV | Four URLs/catalog/query/history/rows-retry-round-trip-hidden import |
| Schema | Single head/history/PG upgrade/CHECK/legacy/v1 flag false |

После возобновления tests из worktree. Backend launcher scripts/run_backend_pytest.ps1 **этого worktree**; REPO_PYTHON существующий interpreter допустим, production venv не модифицировать. Frontend targeted Vitest→type-check→scoped ESLint/Stylelint/theme→build по влиянию. npm run lint содержит --fix: lint:check/non-fixing checks. Broader rerun только по новым changes/failures.

Общие logs для всех карточек: INFO substantial admin safe IDs; WARN expected guard/conflict/stale; ERROR failure без query/tokens/PHI. Reads не log per-row. Mandatory audit actor/typed target/old-new/reason/requestID в change transaction. Operator docs в соответствующем PR; roadmap/исторический DevBrain evidence не переписывать.

## 8. Внедрение, откат и остановка

### Rollout gates

1. Truthful UI/read/schema expand, existing legacy, creation flag false.
2. Все writers classified/upgraded/window-quota-claim PG proof; unresolved mounted writer блокирует v1.
3. Lifecycle/publish/read/UI/compatibility proof, ambiguous binding auto-reassign запрещён.
4. T18 synthetic и full staging validation exact deploy commit.
5. Operator-authorized v1 creation после рабочего дня; plan/CI не разрешение toggle.

Old counter/version-blind writers рядом с v1 запрещены. Versions всех backend processes/workers/adapters и rollback target подтвердить. Precreated future legacy queues сохраняют policy; их список/compatible service scenario документировать до перехода.

### Pre-deploy checklist

Актуальный docs/runbooks/STAGING_VALIDATION.md целиком, включая prerequisites/check0 и дополнительные обязательные пункты. Минимальные десять checks отдельными строками с SHA/env/result/evidence:

| № | Check | Доказательство этого плана сейчас |
|---|---|---|
| 1 | Sentry frontend/backend delivery | NOT_RUN |
| 2 | DR backup restore | NOT_RUN |
| 3 | AI kill-switch →503 | NOT_RUN |
| 4 | AI requires_doctor_confirmation | NOT_RUN |
| 5 | arq enqueue/process | NOT_RUN |
| 6 | Telegram delivery если используется | NOT_RUN; applicability установить |
| 7 | PII code/logs/Sentry | NOT_RUN |
| 8 | Local pre-commit hooks | Historical PR results есть; deploy contour NOT_RUN |
| 9 | Backend unit | T05 applicable CI PASS c04f4102; focused merged-tree tests 24 PASS на fd53206f; deploy staging NOT_RUN |
| 10 | Frontend build/unit | T04 applicable CI PASS b59fff8a; T05 frontend jobs SKIPPED; deploy staging NOT_RUN |

CI/build checklist не заменяют. Не заявлять «система проверена/работает/deployment complete» без required PASS. Docs update не выполняет runtime checks.

### Rollback

- До v1 rows runtime rollback при expanded schema сохранённой.
- После v1 flag off запрещает new v1, existing enforcement продолжается. Counter-blind writer не rollback target.
- Counter/version не удалять/data-losing downgrade не делать/profiles-addresses-targets не reassign.
- UI rollback сохраняет compatible API/URLs; в PR конкретный minimal revert/ограничения.

### Stop/BLOCKED

Зависимый срез остановить при owner-transfer/merge/renumber, parent-public ambiguity requiring choice, unknown historical intent, admission bypass/reset, called-active transfer, overnight, multi-head/destructive upgrade, no mandatory PG/staging, выходе за first-touch.

Read diagnostic conflict не означает auto production repair. Gate/PG proof не обходить mocks. Narrower subtask/sequence change сначала plan/checkpoint с основанием, сохраняя PR-цикл.

## 9. Завершение

T00–T18/подэтапы подтверждённо MERGED; все admissions единая v1 policy; legacy truthful; ambiguities shown/blocked; context survives navigation; UI facts/scope; history/ownership/numbers/queue_time/QR preserved; required evidence для deploy commit.

План/журналы остаются постоянной памятью после завершения. Следующий агент начинает с [RESUME.md](admin-queue-simplification/RESUME.md), сверяет фактическое состояние и готовит безопасный срез T06. T00–T05 не повторять; deferral не переносить в DB gate или будущие PR.
