# План для облачных агентов: надёжность и понятность панели лаборатории

Branch: coordination artifact only; каждый исполняемый PR создаётся от свежего `origin/main`
Created: 2026-09-12

## Settings

- Testing: yes; сначала воспроизводящий тест, затем исправление
- Logging: verbose only at structural boundaries; никогда не логировать ФИО, телефон, дату рождения, результаты, комментарии или другие PHI/PII
- Docs: yes only when operator workflow, API contract or runbook changes; не создавать итоговые отчёты ради отчёта
- Roadmap linkage: none; это отдельная стабилизация лабораторного workflow, не VPS promotion

## Цель

Сделать лабораторный путь предсказуемым и безопасным:

`очередь -> пациент/визит -> назначенные исследования -> создание бланка -> заполнение -> сохранение -> утверждение -> PDF/печать/уведомление -> исправленная версия`

План основан на аудите лабораторного кода и сохранённых UI-снимков. На момент подготовки локальный `HEAD` и `origin/main` содержали одинаковые версии затронутых лабораторных файлов, но каждый агент всё равно обязан заново воспроизвести дефект на своём свежем `origin/main`.

## Канонические владельцы

- RBAC и API-контракт: `backend/app/api/v1/endpoints/lab_reporting.py`, Pydantic-схемы и API-тесты.
- Статусы, неизменяемость, версии и правила финализации: `backend/app/services/lab_reporting/*`.
- Доступ к ORM: `backend/app/repositories/lab_reporting_api_repository.py`.
- Схема хранения: `backend/app/models/lab.py` + новый Alembic revision, только если доказана необходимость менять схему.
- Презентация и локальный draft: `frontend/src/pages/LabPanel.tsx`, `frontend/src/components/laboratory/*`.
- Команды интерфейса разрешаются только через backend `available_actions`/`can_*`; React не должен изобретать переходы статусов.
- Маршрут: `frontend/src/routing/routeRegistry.ts`; его не менять без отдельного доказанного дефекта.

## Общие инварианты

1. Роль `Lab` выполняет лабораторную работу без необходимости иметь профиль врача; роль `Doctor` видит только разрешённые ей визиты; `Admin` сохраняет административный доступ.
2. Утверждённый бланк неизменяем. Исправление создаёт новую версию через `revise`, предыдущая версия остаётся в истории.
3. Старые потребители `lab_results` должны видеть актуальную утверждённую проекцию, не уничтожая показатели других бланков того же заказа.
4. Ни одно успешное сообщение о сохранении не показывается после неуспешного запроса.
5. Комментарии и значения восстанавливаются после повторного открытия и не стираются пустым клиентским состоянием.
6. Выбор шаблона ограничивается серверным service/template resolution. Escape hatch остаётся явным и предупреждающим.
7. Опубликованные версии шаблонов неизменяемы; редактирование идёт через новый draft.
8. Логи, тестовые данные и артефакты используют только явно синтетические идентификаторы и не содержат реалистичных PII/PHI.
9. Каждый PR имеет одну цель. Следующий PR начинается только после зелёных проверок, merge предыдущего и обновления `origin/main`.

## Протокол каждого облачного агента

Перед первым изменением агент обязан вывести в своей задаче:

```text
Execution mode
selected mode: gate или gate_known_root_cause
reason: лабораторный workflow / RBAC / frontend-backend contract является risky domain
risky domain: yes
root cause known: yes/no
scope expectation: narrow
command: C:\final\ai\langgraph\scripts\run_agent_gate.ps1 "<точная задача>" [--known-root-cause "<файл>"]

Initial boundaries
canonical anchor: <файл-владелец>
reference-only files: <список>
first-touch files: <разрешённый список>
validation target: <точные тесты>
stop condition to watch first: <условие>
```

Обязательный цикл:

1. Создать собственный worktree от текущего `origin/main`; не менять ветку в `C:\final`.
2. Проверить `git status`; не трогать чужие изменения и артефакты.
3. Прочитать `AGENTS.md`, `docs/devbrain/PROJECT_MEMORY.md`, `docs/devbrain/DEVBRAIN_STATUS.md`, релевантные skills и канонические файлы задачи.
4. Запустить gate. Если он не включает подтверждённый root-cause, повторить ровно один раз с `--known-root-cause`; при повторном промахе использовать только документированный narrow override.
5. Сначала добавить тест, который падает по ожидаемой причине. Если он проходит на исходном коде, не менять реализацию: проверить предположение, сообщить `finding not reproduced` и остановить PR.
6. Сделать минимальное исправление только в first-touch files.
7. Запустить узкие тесты, затем `git diff --check`. Для видимого UI — Playwright/browser smoke на `5173 -> 18000`.
8. Проверить diff на PII/PHI и на случайные изменения вне границ.
9. Открыть один PR с описанием trigger, прежнего поведения, нового поведения, риска, rollback и фактически выполненных проверок.
10. Не писать «система работает», «deployment complete» или «system verified» без полного `docs/runbooks/STAGING_VALIDATION.md`.

## Последовательность PR

## Tasks

### Phase 1 — безопасность и целостность данных

- [ ] Task/PR 1: восстановить чтение instance и PDF ролью Lab, сохранив doctor ownership.
- [ ] Task/PR 2: актуализировать legacy-проекцию после revise и дополнительных бланков.
- [ ] Task/PR 3: сохранить comments и сделать autosave/optimistic locking достоверными.

### Phase 2 — создание и заполнение бланков

- [ ] Task/PR 4: валидировать текущий draft норм и корректно хранить нулевые границы.
- [ ] Task/PR 5: защитить dirty state и сразу открывать новый шаблон.
- [ ] Task/PR 6: добавить серверно разрешённое действие «Добавить бланк».

### Phase 3 — очередь, печать и сквозное доказательство

- [ ] Task/PR 7: исправить серверную пагинацию и геометрию очереди.
- [ ] Task/PR 8: добавить точный server-rendered PDF preview без побочных эффектов.
- [ ] Final gate: выполнить сквозные backend/frontend/browser проверки после merge выбранных PR.

## Commit Plan

Каждый Task/PR выше является отдельным commit/branch/PR checkpoint. Не объединять
несколько пунктов в один commit и не держать зависимые ветки параллельно. Рекомендуемые
сообщения: `fix(lab): allow lab staff to read reports`, `fix(lab): refresh legacy result projection`,
`fix(lab): preserve report draft integrity`, `fix(lab): validate template reference rules`,
`fix(lab): guard unsaved laboratory edits`, `feat(lab): add another allowed report`,
`fix(lab): paginate and measure the lab queue`, `feat(lab): preview server-rendered reports`.

### PR 1 — восстановить чтение бланка и PDF ролью Lab

**Цель:** доказать и исправить расхождение, при котором `POST /lab/report-instances` разрешён роли `Lab`, а последующий `GET /lab/report-instances/{id}` и `/pdf` могут вернуть 403, если у пользователя нет Doctor-профиля.

**Первый тест:** создать обычного активного пользователя с `role="Lab"`, без Doctor row; создать синтетический бланк через разрешённый setup; доказать, что он может получить instance и PDF. Сохранить существующий тест, что Doctor не читает чужой визит.

**Разрешённые файлы:**

- `backend/app/api/v1/endpoints/lab_reporting.py`
- `backend/tests/test_lab_reporting_api.py`
- при необходимости только существующий узкий auth fixture в `backend/tests/conftest.py`

**Запрещено:** расширять доступ Registrar/Cashier/Patient; менять глобальный `require_roles`; ослаблять doctor ownership; менять очередь или frontend.

**Желаемый контракт:** `Admin` и `Lab` проходят lab-instance read/PDF guard; `Doctor` проходит только ownership guard; остальные роли отсекаются зависимостью endpoint.

**Проверки:**

```powershell
C:\final\scripts\run_backend_pytest.ps1 tests/test_lab_reporting_api.py -q
git diff --check
```

**Стоп:** если продуктовая политика требует ограничивать Lab по лаборатории/филиалу, а в данных нет канонического scope, не заменять его полным доступом молча; оформить блокер.

### PR 2 — исправить актуализацию legacy-проекции после revise и дополнительных бланков

**Цель:** `lab_results`, читаемая EMR/mobile/статистикой, отражает последнюю утверждённую версию каждого показателя и не блокирует новый бланк из-за наличия любой строки того же `order_id`.

**Первый тест:**

- финализировать бланк A;
- создать `revise`, изменить один синтетический показатель, финализировать;
- доказать, что legacy consumer видит новое значение;
- создать/финализировать дополнительный бланк B с другим `test_code` для того же order и доказать, что показатели A не исчезли.

**Предпочтительный минимальный контракт:** upsert проекции по `(order_id, test_code)`: совпадающий показатель обновляется значением последней финализированной версии, отличающиеся показатели сохраняются. Сначала проверить все потребители и коллизии test_code.

**Разрешённые файлы:**

- `backend/app/services/lab_reporting/_finalize.py`
- `backend/app/repositories/lab_reporting_api_repository.py`, только если нужен репозиторный helper
- `backend/tests/unit/test_lab_reporting_service.py`
- узкий integration/API test только если unit test не доказывает consumer contract

**Запрещено:** удалять все `LabResult` по `order_id`; менять публичный DTO; вводить migration без доказанной невозможности корректного upsert; переписывать EMR integration.

**Проверки:**

```powershell
C:\final\scripts\run_backend_pytest.ps1 tests/unit/test_lab_reporting_service.py tests/test_lab_reporting_api.py::test_lab_reporting_api_flow -q
git diff --check
```

**Стоп:** если одинаковый `test_code` законно означает два параллельных результата одного заказа, upsert-контракт неоднозначен. Тогда подготовить отдельный schema proposal (`source_report_instance_id`/lineage), но не делать миграцию в этом PR.

### PR 3 — обеспечить целостность draft: комментарии, autosave и optimistic locking

**Цель:** повторное открытие не теряет комментарии; autosave сообщает успех только после успеха; два лаборанта не перезаписывают друг друга; изменение signer и values в одном сохранении не конфликтует с собственным устаревшим timestamp.

**Первый набор тестов:**

- `useLabReportState` гидратирует `field_key__comment` из materialized field comment;
- сохранение повторно открытого draft отправляет прежний комментарий, а не `null`;
- autosave failure не обновляет `lastAutoSave` и оставляет dirty/retry состояние;
- после bulk value update меняется version token (`updated_at` или иной существующий token), а stale token получает 409;
- последовательное сохранение signer + values использует timestamp из ответа первого запроса.

**Разрешённые файлы:**

- `frontend/src/components/laboratory/hooks/useLabReportState.ts`
- `frontend/src/components/laboratory/LabReportWorkbench.tsx`
- соответствующие существующие тесты в `frontend/src/components/laboratory/**/__tests__`
- `backend/app/services/lab_reporting/_instances.py`
- `backend/tests/unit/test_lab_reporting_service.py` или `backend/tests/test_lab_reporting_api.py`
- `frontend/src/api/labReporting.ts` только если нужно корректно передать новый version token без изменения публичной семантики

**Запрещено:** вводить новый глобальный state manager; сохранять PHI в localStorage; ослаблять 409 до last-write-wins; добавлять бесконечные retry.

**UX:** при 409 показать локализованное действие «Обновить актуальную версию»; не заменять введённый draft автоматически без явного решения пользователя.

**Проверки:**

```powershell
C:\final\frontend\node_modules\.bin\vitest.cmd run src/components/laboratory --reporter=dot
C:\final\scripts\run_backend_pytest.ps1 tests/unit/test_lab_reporting_service.py tests/test_lab_reporting_api.py::test_lab_reporting_api_flow -q
git diff --check
```

**Стоп:** если исправление требует общего transaction/save DTO, вынести контракт в отдельный PR и не маскировать гонку frontend workaround.

### PR 4 — сделать валидацию норм шаблона достоверной

**Цель:** Save/Publish валидирует именно текущий draft из structured editor, корректно принимает нулевые границы и блокирует `low >= high` до запроса.

**Первый набор тестов:**

- пользователь меняет старый диапазон `1..10` на `10..1`; publish заблокирован;
- `0..10` сохраняется как `0..10`, а не `null..10`;
- invalid JSON в developer mode даёт inline error, сохраняет введённый текст и не отправляет запрос;
- backend также отвергает structurally invalid reference/highlight/visibility rule, если сейчас доверяет клиенту.

**Разрешённые файлы:**

- `frontend/src/components/laboratory/LabTemplateWorkbench.tsx`
- `frontend/src/components/laboratory/templateEditor/ReferenceRuleEditor.tsx`
- `frontend/src/components/laboratory/templateEditor/utils.ts`
- существующие тесты `LabTemplateWorkbench*`
- `backend/app/services/lab_reporting/_versions.py` и узкий backend test только если server validation отсутствует

**Запрещено:** менять формат rule engine без отдельного контракта; удалять developer mode; переписывать весь template editor.

**Проверки:** targeted Vitest для template editor; targeted backend service tests, если менялся backend; `git diff --check`.

**Стоп:** если UI и backend используют разные rule schema, сначала зафиксировать Pydantic DTO/contract; не поддерживать две формы угадывающей нормализацией.

### PR 5 — защитить несохранённые изменения и завершить путь создания шаблона

**Цель:** смена пациента, instance или шаблона не уничтожает draft; новый шаблон сразу открывается в редакторе.

**Ожидаемое поведение:**

- при dirty report/template переход показывает единый ConfirmDialog: сохранить, выйти без сохранения, отменить;
- отмена оставляет пользователя и введённые значения на месте;
- успешное сохранение продолжает изначально выбранный переход;
- после `createTemplate` UI использует возвращённый id, обновляет список и выбирает созданный шаблон;
- browser back и URL params не обходят guard.

**Разрешённые файлы:**

- `frontend/src/pages/LabPanel.tsx`
- `frontend/src/components/laboratory/LabReportWorkbench.tsx`
- `frontend/src/components/laboratory/LabTemplateWorkbench.tsx`
- один новый узкий reusable hook только внутри `frontend/src/components/laboratory/hooks/`, если без него появляется дублирование
- focused component tests и один mocked Playwright workflow spec

**Запрещено:** менять React Router registry/aliases; сохранять черновики в браузерное постоянное хранилище; менять backend статусы.

**Проверки:** targeted Vitest; mocked Playwright: dirty value -> select another queue patient -> Cancel preserves input; create template -> returned template selected; `git diff --check`.

### PR 6 — добавить явное создание следующего бланка для того же визита

**Цель:** после открытия/финализации одного бланка лаборант видит действие «Добавить бланк», выбирает только разрешённый оставшийся шаблон и создаёт второй instance без потери истории первого.

**Сначала доказать:** backend уже разрешает несколько instances на одном visit/order и корректно ограничивает template resolution. Если нет — остановиться на контрактном dossier, не добавлять frontend-кнопку.

**Контракт UI:**

- действие доступно из patient/report context, а не скрыто за возвратом в очередь;
- список показывает назначенные услуги, уже созданные бланки и ещё доступные шаблоны;
- нельзя случайно создать дубликат того же template для того же назначения без явного серверного разрешения;
- открытие нового бланка не заменяет историю предыдущего;
- разрешение команды исходит из backend fact (`available_templates`/`available_actions`), а не вычисляется React по статусам.

**Предварительные first-touch:**

- `backend/app/services/lab_reporting/_templates.py` или `_context.py`
- `backend/app/schemas/lab_reporting.py`
- `backend/app/api/v1/endpoints/lab_reporting.py`
- `frontend/src/api/labReporting.ts`
- `frontend/src/components/laboratory/LabReportWorkbench.tsx`
- focused API/component/Playwright tests

**Стоп:** если требуется решить допустимость повторного одинакового исследования, это продуктовая политика. Не выбирать её агентом.

### PR 7 — исправить серверную пагинацию и геометрию очереди

**Цель:** `total` означает общее количество, `entries` содержит только requested slice, длинные карточки не перекрываются, поиск/фильтр честно описывает область поиска.

**Первый набор тестов:**

- при 120 entries запрос `limit=50&offset=50` возвращает 50 элементов и `total=120`;
- следующий запрос возвращает 20;
- UI не показывает отрицательное remaining и не делает повторные concurrent load-more;
- карточки разной высоты измеряются virtualizer или заменяются на более простой корректный список для page size 50;
- длинная услуга не перекрывает следующую карточку на 375/768/1280 px.

**Разрешённые файлы:**

- `backend/app/api/v1/endpoints/lab_reporting.py`
- при необходимости lab-specific service/repository helper, без правки registrar ownership
- `frontend/src/pages/LabPanel.tsx`
- `frontend/src/components/laboratory/VirtualizedQueueList.tsx`
- `frontend/src/components/laboratory/LabQueueWorkbench.tsx`
- `frontend/src/pages/lab.css`
- targeted API/Vitest/Playwright tests

**Запрещено:** менять backend canonical queue ordering; сортировать server queue во frontend режиме `default`; массово редизайнить панель.

**Стоп:** если registrar facade уже пагинирует вложенные очереди с другой семантикой, сначала определить единый owner total/order.

### PR 8 — точный PDF preview до публикации/утверждения

**Цель:** пользователь видит серверный A4-рендер того же движка, который будет печататься, без необходимости утверждать клинический результат.

**Разделить два сценария:**

1. Template preview: синтетические placeholder values, никаких данных реального пациента.
2. Draft report preview: текущие сохранённые значения конкретного instance; доступ только Admin/Lab и только в текущем клиническом контексте.

**Требования:** отдельный preview contract; `Content-Disposition: inline`; watermark «Черновик» для неутверждённого результата; preview не вызывает `mark-printed`, уведомление или финализацию; renderer один и тот же с финальным PDF; тест длинных строк, переноса страницы и подписей.

**Предварительные first-touch:**

- `backend/app/services/lab_report_pdf_service.py`
- `backend/app/api/v1/endpoints/lab_reporting.py`
- `backend/app/schemas/lab_reporting.py`, если нужен explicit preview DTO
- `frontend/src/api/labReporting.ts`
- `frontend/src/components/laboratory/templateEditor/PreviewTab.tsx`
- `frontend/src/components/laboratory/LabReportWorkbench.tsx`
- backend PDF tests и Playwright preview smoke

**Стоп:** не отправлять unsaved patient values через новый endpoint без явного контракта. Первая версия draft preview может требовать Save Draft перед preview.

## Отдельный product decision gate — учёт пробирок и образцов

Не включать в PR 1–8. Сначала отдельный dossier должен ответить:

- нужен ли barcode/accession number;
- какие статусы обязательны: ordered, collected, received, rejected, recollect, processing, completed;
- кто и где фиксирует забор и приём;
- допустимы ли несколько образцов на один заказ;
- причины брака и audit requirements;
- печатаются ли этикетки и каким принтером;
- интеграция с внешними анализаторами сейчас или позже.

Если владелец продукта подтверждает scope, это отдельная серия PR с цепочкой `model -> schema -> Alembic -> repository -> service -> API -> UI -> PostgreSQL validation`. DB-изменение всегда идёт через gate и новую migration; никакого ad-hoc DDL.

## Финальный интеграционный gate после PR 1–8

Запускать только после merge всех выбранных PR и синхронизации main:

- backend lab API/service tests;
- frontend lab Vitest tests;
- mocked Playwright полный путь: очередь -> создать -> заполнить -> сохранить -> утвердить -> preview/PDF -> revise -> проверить историю;
- живой smoke на синтетических данных через `5173 -> 18000`, если доступен disposable PostgreSQL;
- `git diff --check` в каждом PR;
- полный `docs/runbooks/STAGING_VALIDATION.md` только перед deploy или утверждением, что вся система проверена.

## Готовый master prompt для облачного координатора

```text
Ты работаешь в репозитории C:\final над панелью лаборатории. Выполни программу из
.ai-factory/plans/codex-lab-workflow-hardening-plan.md.

Режим HANDOFF_MODE=1, если координатор его предоставляет. Не задавай вопросы,
когда ответ уже определён планом и каноническим кодом. Не выполняй все пункты в
одном PR. Один запуск/агент = один PR из последовательности PR 1 -> PR 8.

Перед каждым PR:
1) дождись, что предыдущий PR green и merged;
2) fetch origin;
3) создай отдельный worktree и ветку codex/lab-<short-purpose> от свежего origin/main;
4) прочитай AGENTS.md, PROJECT_MEMORY.md, DEVBRAIN_STATUS.md и релевантные skills;
5) выведи обязательный Execution mode / Initial boundaries block;
6) запусти scripts/run_agent_gate.ps1 с точной задачей;
7) сначала добавь воспроизводящий тест.

Если исходный код уже проходит воспроизводящий тест, не делай speculative fix:
сообщи finding not reproduced с commit SHA и останови этот PR. Если требуется
файл вне first-touch, сработал stop condition или появилась продуктовая
неоднозначность, остановись и верни blocker; не расширяй scope молча.

Backend соблюдает endpoint -> service -> repository -> PostgreSQL/Alembic.
Frontend только отображает backend facts и отправляет команды. Не ослабляй RBAC,
finalized immutability, doctor ownership, template resolution или auditability.
Не логируй PHI/PII и не используй реалистичные персональные данные в fixtures.

После изменения запусти только указанные узкие проверки, затем git diff --check.
Для UI добавь/запусти browser smoke. В PR body укажи trigger, before/after,
scope, risk, rollback, exact validation. Не начинай следующий PR сам: верни URL,
SHA, checks и ожидай merge/status от координатора.

Начни с первого незавершённого PR в плане. Product decision gate по образцам и
пробиркам не реализуй без отдельного подтверждённого решения владельца продукта.
```

## Шаблон промпта для одного облачного агента

```text
Выполни только PR <N> из
.ai-factory/plans/codex-lab-workflow-hardening-plan.md.

Base: свежий origin/main.
Branch: codex/lab-<purpose>.
Ownership: только first-touch files этого PR.
Reference-only: остальные laboratory, queue, EMR и migration файлы.

Сначала воспроизведи дефект focused test. Если тест не падает на base, остановись
с evidence и не меняй runtime. Затем внеси минимальный fix, сохрани backend SSOT,
RBAC, immutability и PII masking. Не делай adjacent cleanup.

В конце верни строго:
- Changed
- Why
- Validation run: команды и точные результаты
- Result
- Scope check
- Stop conditions hit
- Remaining risk
- PR URL и head SHA, если PR открыт

Не используй формулировки deployment complete/system verified/it works без всех
10 проверок STAGING_VALIDATION.md.
```

## Критерий завершения программы

Программа завершена, когда выбранные PR слиты по порядку, их узкие проверки зелёные, полный пользовательский путь доказан browser smoke, а нерешённые product decisions явно вынесены из runtime scope. Наличие зелёного CI само по себе не означает, что лабораторный процесс проверен целиком.
