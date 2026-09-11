# Журнал выполнения: регистратура и очереди

[Определения задач](../codex-registrar-queue-remediation-plan.md) · [Старт агента](CLOUD-START.md) · [Приемка](ACCEPTANCE.md)

Это единственный источник текущих статусов. Не вести отдельный конкурирующий чеклист в чате, issue или другой PLAN.md. Критерии задачи находятся в основном плане; история доказательств — здесь. Наличие отметки без проверяемого свидетельства не закрывает задачу.

## Точка продолжения

- Обновлено: 2026-09-11, RQ-01 базис зафиксирован (VERIFIED в PR, DONE после merge-сверки).
- План: v1; исходный main аудита: `22febf376f710a3b3b6ce57ac85de589ebba3f21`; актуальный проверенный базис: `be6012b18484a7221e704afcd0c04ce33c4a9cf4`.
- Реализация: 0/30 runtime-задач закрыто; RQ-01 VERIFIED (сверка базиса — см. E-003).
- Активная runtime-задача: нет. Владелец RQ-01: агент среза 2026-09-11.
- Подготовительный docs PR [#3157](https://github.com/drsapaev/final/pull/3157) **merged** в main (`be6012b18`); план доступен в fresh main — runtime-работа от fresh main разрешена.
- Следующий шаг: **RQ-02** (минимальная незаблокированная: direct_execute, first-touch вне #3114). Перед стартом сверить merge RQ-01 и его фактический SHA.
- Дрейф плана, зафиксированный RQ-01: QD-2A (0055–0059) уже merged через PR #3093 (`1f775cb`), поэтому открытый PR #3077 выглядит дубликатом/суперсeded — не мержить без сверки содержимого; F-10/F-16 частично смягчены; F-14 частично изменен. Подробности в E-003.
- Открытые продуктовые решения: D-01…D-07 (все OPEN). Они не блокируют независимые fixes.
- Среда: Node 24/npm/Playwright-chromium — frontend unit/MOCK доступны; pwsh 7.4.6 установлен user-local, gate валидирован; Python 3.12 (venv есть, зависимости backend НЕ установлены); PostgreSQL и Redis отсутствуют → PG/REAL_API-части соответствующих задач BLOCKED (см. E-003, частные blockers).
- Публикация состояния: проверять remote HEAD перед передачей; не считать локальный checkpoint доступным облаку.

## Статусы и правила закрытия

| Статус | Значение | Следующий шаг |
|---|---|---|
| TODO | Работа не начата; зависимости могут быть еще не готовы | Проверить актуальность и зависимости |
| IN_PROGRESS | Назначен владелец, branch/base и узкий срез | Продолжить этот срез |
| IMPLEMENTED | Изменения есть, обязательная проверка еще не завершена | Запустить/исправить проверки |
| VERIFIED | Все проверки именно этого среза прошли на записанном HEAD | Подготовить PR с evidence |
| PR_OPEN | PR открыт; CI/review/merge еще не завершены | Исправить красный CI, обработать review |
| BLOCKED | Записаны точная причина и условие разблокирования | Устранить prerequisite/получить решение; не подменять PASS |
| DONE | Исправление merged, проверки относятся к merged содержимому; для анализа/проверки сохранен доказанный результат | Можно брать зависимую задачу |
| DONE_EQUIVALENT | Исправлено другим merged PR либо гипотеза опровергнута проверкой | Указать PR/SHA/сценарий и почему критерий выполнен |
| DEFERRED_BY_OWNER | Пользователь явно исключил/отложил объем, записано решение | Не считать исправленным; dependent-план пересогласовать |

DONE требует: критерий из плана выполнен; узкие тесты и соответствующие S-сценарии; diff check; ссылка PR и merge SHA для code change; отсутствие красных required checks; evidence проверяет финальное содержимое. Если после проверок изменился runtime-код, проверить затронутую часть снова. Пропущенный тест не становится успешным.

Статус DONE нельзя закоммитить в PR с будущим merge SHA. Внутри PR оставить PR_OPEN/VERIFIED и ссылку; в начале следующего разрешенного цикла сверить merge и обновить журнал. Это обычное согласование фактов, не повторная реализация. Evidence для verification-only задачи тоже должен быть сохранен в доступном репозитории/PR.

Если у задачи появилось несколько children, parent остается IN_PROGRESS/BLOCKED до их завершения. Нельзя считать parent готовым по одному дочернему PR. Новый дочерний ID, owner, first-touch и acceptance сначала записываются ниже.

## Реестр задач

Колонка «Зависимости» — краткая подсказка; условия продуктовых решений уточняются в основном плане. Owner/branch/PR заполнять до runtime-работы, evidence — на каждом checkpoint.

| ID | Задача | Зависимости | Статус | Owner / branch / PR | Evidence |
|---|---|---|---|---|---|
| RQ-01 | Актуальный базис | — | VERIFIED | codex/rq-01-baseline-verification / PR после checkpoint | E-003 |
| RQ-02 | Поиск пациента | RQ-01 | TODO | — | — |
| RQ-03 | Услуги мастера | RQ-01 | TODO | — | — |
| RQ-04 | Атомарное отделение | RQ-01; проверить #3114 | TODO | — | — |
| RQ-05 | Обязательный врач | RQ-01 | TODO | — | — |
| RQ-06 | Профиль/тег/отделение | RQ-01 | TODO | — | — |
| RQ-07 | Категории корзины | RQ-03, RQ-05 | TODO | — | — |
| RQ-08 | Допустимые врачи и теги | RQ-05, RQ-06; проверить #3114 | TODO | — | — |
| RQ-09 | Публичная видимость QR | RQ-01; проверить #3114 | TODO | — | — |
| RQ-10 | Частичный QR-результат | RQ-01 | TODO | — | — |
| RQ-11 | Срок текущего QR | RQ-01 | TODO | — | — |
| RQ-12 | Удаление профиля | RQ-12.a + RQ-12.b ниже | TODO | — | — |
| RQ-13 | Жизненный цикл отделения | RQ-04, RQ-12; D-06; проверить #3114 | TODO | — | — |
| RQ-14 | QR и регистратура: владелец | RQ-03, RQ-08, RQ-09; D-01; проверить #3114 | TODO | — | — |
| RQ-15 | Ресурсная очередь | RQ-01; merge/координация #3114 | TODO | — | — |
| RQ-16 | Адресуемое направление | RQ-06, RQ-12, RQ-13, RQ-14, RQ-15; D-01, D-03, D-04 | TODO | — | — |
| RQ-17 | Путь настройки | RQ-05, RQ-06, RQ-16; D-01 | TODO | — | — |
| RQ-18 | QR новой очереди | RQ-09, RQ-10, RQ-11, RQ-16, RQ-17; D-03 | TODO | — | — |
| RQ-19 | Читаемые вкладки/ARIA | RQ-01 | TODO | — | — |
| RQ-20 | Название и навигация | RQ-19; D-07 при смене маршрутов | TODO | — | — |
| RQ-21 | Счетчики и пустой поиск | RQ-21.a + RQ-21.b ниже | TODO | — | — |
| RQ-22 | Сбой обновления списка | RQ-01 | TODO | — | — |
| RQ-23 | Эффективные настройки | RQ-13, RQ-14, RQ-15; D-06 | TODO | — | — |
| RQ-24 | Связанные панели | RQ-24.a + RQ-24.b ниже | TODO | — | — |
| RQ-25 | Исключения рабочего дня | RQ-25.a + RQ-25.b ниже | TODO | — | — |
| RQ-26 | Импорт/экспорт профилей | RQ-26.a + RQ-26.b ниже | TODO | — | — |
| RQ-27 | Обновление другой сессии | RQ-27.a + RQ-27.b ниже | TODO | — | — |
| RQ-28 | Инструкция персоналу | RQ-17, RQ-18, RQ-20, RQ-23, RQ-26, RQ-27; D-07 | TODO | — | — |
| RQ-29 | Сквозная приемка | RQ-02…RQ-28 | TODO | — | — |
| RQ-30 | Staging handoff | RQ-29 | TODO | — | — |

## Решения владельца продукта

Значения: OPEN / PROPOSED / APPROVED / REJECTED. Ответ должен содержать конкретное поведение и источник согласования; рекомендации из плана не являются APPROVED.

| ID | Статус | Принятое поведение | Кто / когда / источник | Разблокированные задачи |
|---|---|---|---|---|
| D-01 | OPEN | — | — | — |
| D-02 | OPEN | — | — | — |
| D-03 | OPEN | — | — | — |
| D-04 | OPEN | — | — | — |
| D-05 | OPEN | — | — | — |
| D-06 | OPEN | — | — | — |
| D-07 | OPEN | — | — | — |

## Дочерние срезы и изменение границ

Срезы ниже запланированы заранее, чтобы исправление текущих дефектов не ждало новой продуктовой модели. Наследуют canonical/first-touch/reference/stop/logging/rollback родителя только в своей описанной части; перед правкой сузить точные файлы через pre-work/gate. Acceptance родителя применяется к текущему контракту для .a и к принятому новому контракту для .b. Если .a находит несколько дефектов в разных владельцах, создать RQ-NN.a.1 и далее с отдельными PR; проверка без дефекта закрывается evidence.

| Child ID | Результат | Зависимости | Статус | Owner / branch / PR / evidence |
|---|---|---|---|---|
| RQ-12.a | Сохранить тег, используемый другим профилем, при текущем delete | RQ-01 | TODO | — |
| RQ-12.b | Согласованный lifecycle/preview/archive/delete | RQ-12.a; D-02 | TODO | — |
| RQ-21.a | Отличить «Нет совпадений» от пустой очереди | RQ-01, RQ-02 | TODO | — |
| RQ-21.b | Согласованные счетчики и единицы | RQ-21.a, RQ-20; D-07 | TODO | — |
| RQ-24.a | Проверить существующий путь по ролям; закрыть доказанные дефекты | RQ-01 | TODO | — |
| RQ-24.b | Проверить путь нового target/resource | RQ-24.a, RQ-08, RQ-14, RQ-15, RQ-18, RQ-21 | TODO | — |
| RQ-25.a | Проверить существующие повторы/семью/отмену/оплату; закрыть дефекты | RQ-01 | TODO | — |
| RQ-25.b | Принятые пакеты/владельцы/замена и изменения днем | RQ-25.a, RQ-10, RQ-14, RQ-24; D-04/D-05 для расширения | TODO | — |
| RQ-26.a | CSV текущего контракта без потери полей | RQ-01 | TODO | — |
| RQ-26.b | CSV после нового target/lifecycle | RQ-26.a, RQ-06, RQ-12, RQ-16 | TODO | — |
| RQ-27.a | Две сессии существующих профилей, точечное обновление | RQ-01 | TODO | — |
| RQ-27.b | Новое направление/настройки и сохранение открытого мастера | RQ-27.a, RQ-13, RQ-17, RQ-23 | TODO | — |

Parent DONE только после обоих children; parent и children не складываются при расчете процента: знаменатель основного плана — 30 задач, детализация не повышает completion искусственно. Для нового среза добавить:

- ID и parent; конкретная причина разделения.
- Canonical anchor; reference-only; разрешенные first-touch; denied paths.
- Зависимости и продуктовые решения.
- Наблюдаемый результат; тесты и S-ID.
- Gate/handoff command и результат, stop conditions.
- Owner, branch, PR и статус.
- Logging L-UI/L-DOMAIN/L-EVIDENCE.
- Откат; влияет ли срез на дальнейшие задачи.

## Журнал доказательств

### E-000 — исходный аудит, до реализации

- Дата: 2026-09-11; SHA: `22febf376f710a3b3b6ce57ac85de589ebba3f21`.
- Действия: чтение кода/контрактов; никакого изменения runtime или production-данных.
- Из `frontend/` запущено:
  `node node_modules/vitest/vitest.mjs run src/pages/registrar/__tests__/registrarWorklistRows.test.ts src/components/navigation/__tests__/Tabs.a11y.test.tsx src/components/wizard/__tests__/AppointmentWizardV2.contract.test.tsx src/components/admin/__tests__/UserModal.onboarding.test.tsx --no-cache --reporter=dot`.
- Результат: 4 файла, 41 тест PASS. Были ожидаемые mocked offline warnings и предупреждение React о closable; они не являются доказательством реального сетевого отказа.
- Чистый helper getWizardDepartmentFilterKeys дополнительно вызван на SYNTHETIC примерах: null -> [""] -> пустой список; ecg/echokg + department cardiology -> пустой список; neurology -> ожидаемая услуга.
- `git diff --check`: PASS, исходный main чистый.
- NOT_RUN: backend DB, PostgreSQL constraints/locking/migrations, полный browser/API workflow и staging checklist. localhost:5173 был недоступен.
- Вывод: основание для плана, **ни одна задача RQ этим не закрыта**.

### E-001 — проверка переносимости и координации плана

- Чтением подтверждено: run_python.ps1 поддерживает Linux venv/PATH python3; gate запускается через pwsh и stdlib Python.
- Backend test_db использует SQLite; mock Playwright не равен реальному API. См. CLOUD-START.
- PR #3114 открыт на момент подготовки; HEAD обновлялся. Его состояние проверять заново перед пересекающимися задачами.
- PR #3142 merged и входит в исходный main.
- Изменений приложения и запусков новых тестов эта проверка не включала.

### E-002 — подготовка и публикация документов

- Дата: 2026-09-11. Docs commit: `19904399f1147605e8f4eaec94680c3f28067cd2`; PR #3157. Эта запись добавлена отдельным документационным checkpoint того же PR.
- PASS: структурные assertions через Node (stdin): 30 уникальных родителей, 12 детей, 24 замечания с владельцами-задачами, 28 сценариев, отсутствие циклов; 12 относительных ссылок; 73 source-path references, из которых 4 явно обозначены как будущие новые тесты.
- PASS: `git diff --cached --check` перед коммитом; область — только четыре документа этого комплекта.
- PASS: из своего worktree `.\scripts\run_python.ps1 -PythonArgs @('scripts/run_pr_review_gate_checks.py', '--body-file', '.registrar-plan-pr-body.md')`: 19 тестов валидатора, образцы и окончательный PR body. Временный body не является частью Git-комплекта; опубликован в PR.
- Дополнительное read-only review исправило блокировки независимых задач, cloud prerequisites и merge reconciliation. Устаревшая ссылка на отсутствующий frontend/AGENTS.md исключена из обязательных источников.
- NOT_RUN: новые тесты приложения, PostgreSQL/REAL_API/browser и staging; runtime не менялся. GitHub checks/merge сверять непосредственно в PR.
- Результат: план доступен удаленному агенту, задачи RQ остаются TODO. Следующий шаг — RQ-01; runtime с fresh main после merge плана, если пользователь не назначил другую базу.

### E-003 — RQ-01: сверка актуального базиса, владельцев и среды

- Task / child: RQ-01 (dossier, без runtime-правок).
- UTC timestamp: 2026-09-11, срез облачного агента.
- Repo branch: `codex/rq-01-baseline-verification`; Base SHA / tested HEAD: `be6012b18484a7221e704afcd0c04ce33c4a9cf4` (= origin/main на момент среза, чистый checkout).
- B0 сверка GitHub (read-only API): открытых PR — 23 (авторы: drsapaev, dependabot[bot], vercel[bot]; сторонних авторов нет). PR #3157 (план) **merged** 2026-09-11T02:57:43Z → merge commit `be6012b18` = текущий main. PR #3114 (QD-2C) **открыт**, head `d4eb4cfd7481`, 64 файла, 40 коммитов; карта пересечений с RQ: затрагивает first-touch/якоря RQ-04 (`admin_departments/_helpers.py`), RQ-08 (`doctor_integration/_queue_ops.py`), RQ-09/18 (`qr_queue/_queue_ops.py`, `_tokens.py`), RQ-14 (`queue_svc/_operations.py` +327/−104, `test_queue_allocator_characterization.py`), RQ-15 (`morning_assignment.py`), RQ-24 (`display_websocket*`), RQ-25 (`test_qr_queue_full_update.py`, `test_qr_queue_join.py`). Не пересекаются: RQ-02, RQ-03, RQ-05 (`_services_doctors.py` не в списке), RQ-06, RQ-07, RQ-10 (`qr_queue/_sessions.py` не в списке), RQ-11, RQ-12.a, RQ-19–RQ-22, RQ-26.a, RQ-27.a.
- Сверка F-01…F-24 по исходникам `be6012b18` (трассировка каждого якоря): 21 STILL_PRESENT; частично изменены F-10 (TTL 5–15 мин в `queue_svc/_base.py:79-80` и скачиваемый PNG без предупреждения — как в плане, но на экране теперь отображается «Действует до»), F-16 (ARIA/aria-describedby/sr-only добавлены, но `@media (max-width:768px){.tab-label{display:none}}` в `Tabs.css:274-275` остается), F-14 (модель `QueueResource` и миграции 0055–0059 в main, но `morning_assignment.py:518-530` все еще использует синтетические `*_resource` аккаунты). Тест, закрепляющий дефект F-01, на месте: `registrarWorklistRows.test.ts:150-155` («PRE-EXISTING QUIRK… Pinned as-is»).
- Дрейф против плана: QD-2A landed не через открытый PR #3077, а через **merged PR #3093** (commit `1f775cb`, миграции 0055–0059 на main, дополнительно 0060 visit_reminder). PR #3077 открыт и, судя по заголовку/содержимому, superseded — не мержить без поэлементной сверки; владелец #3114/#3077 должен подтвердить. Это снимает премису плана «0058 не merged» для RQ-15: его первый шаг (проверка merged реализации ресурсов) стал выполнимым.
- Матрица прав вызова (существующие различия сохранены, ничего не расширять):
  - doctor_integration call/start-visit/complete: `require_roles("Admin","Doctor","Registrar","Cashier","cardio","cardiology","Cardiologist","derma","dentist","Lab")` (`doctor_integration/_queue_ops.py:250-261, :392-403, :505-516`); бизнес-проверка владельца очереди или той же специальности (`:302-318`).
  - QR `POST /queue/{specialist_id}/call-next` и status/entries-мутации: `require_roles("Admin","Doctor","Registrar")` + `_ensure_doctor_can_mutate_specialist_queue` (`qr_queue/_queue_ops.py:48`, `_entries.py:21,97,170,221`).
  - QR-токены: generate — Admin/Doctor/Registrar (`_tokens.py:16`); generate-clinic — только Admin/Registrar (`_tokens.py:84`).
  - Display quick call-next: Admin/Doctor/Registrar (`display_websocket.py:361`).
  - Queue profiles: чтение Admin/Registrar/Doctor/Cashier/Lab (`_queue_profiles.py:45`); create/update/delete/reorder — только Admin (`:276, :344, :402, :455`).
  - Публичный join (`/queue/qr-tokens/{token}/info`, `/queue/join/start|complete`) — без require_roles, токен-гейт (`_join.py`).
  - Зафиксированное расхождение (не баг-фиксить здесь): кассир может вызвать через doctor-integration путь, но не через канонический QR call-next.
- Команды и результаты (working dir `/home/z/repo/frontend`):
  - `npm ci --legacy-peer-deps` → EXIT=0.
  - `node node_modules/vitest/vitest.mjs run src/pages/registrar/__tests__/registrarWorklistRows.test.ts src/components/navigation/__tests__/Tabs.a11y.test.tsx src/components/wizard/__tests__/AppointmentWizardV2.contract.test.tsx src/components/admin/__tests__/UserModal.onboarding.test.tsx --no-cache --reporter=dot` → **4 files / 41 tests PASS** (2.81s). Найденные тесты отделены от запущенных: запущены ровно 4 файла E-000; прочие 9 backend-файлов только локализованы (все существуют), не запускались.
  - `pwsh -NoProfile -File ./ai/langgraph/scripts/run_agent_gate.ps1 "RQ-01: …"` → `{"result":"stop","reason":"no first-touch files could be resolved…"}` (корректно для dossier без путей); повтор с `--known-root-cause frontend/src/pages/registrar/registrarWorklistRows.ts` → валидный JSON (`first_touch_files`, `validation_targets`, `stop_conditions`). Gate-инструментарий работоспособен.
  - `git diff --check` — PASS (перед checkpoint-коммитом).
- Инвентаризация тестов (найдены, НЕ запускались): `backend/tests/characterization/test_registrar_wizard_queue_characterization.py`, `test_queue_allocator_characterization.py`, `backend/tests/integration/test_registrar_services_grouping.py`, `test_qr_queue_join.py`, `test_queue_resource_expand.py`, `test_queue_resource_seed_backfill.py`, `test_queue_resource_sentinel.py`, `test_multi_doctor_same_specialty_isolation.py`, `backend/tests/unit/test_queue_time_window.py`.
- Среда: Node v24.19.0 (CI — Node 20; дрейф некритичен, тесты зеленые); Playwright chromium в кэше → browser MOCK доступен; pwsh 7.4.6 установлен user-local (`~/.local/share/powershell`, без глобальных настроек); Python 3.12.14 (формально ≥3.11 по CLOUD-START, но CI — 3.11.10; зависимости backend не установлены).
- Acceptance S-IDs: не применимы к RQ-01 (dossier). MOCK/REAL_API маркировка: frontend vitest — MOCK-уровень окружения; REAL_API — NOT_RUN.
- NOT_RUN и почему: backend pytest (зависимости backend не установлены в venv — bootstrap по P0 не выполнялся в этом срезе); PostgreSQL/Alembic-проверки (PostgreSQL отсутствует в среде); REAL_API/browser-over-backend (Redis и disposable backend отсутствуют); e2e Playwright suite (полнота — gate merge UI PR, не требуется RQ-01).
- Частные blockers (не блокируют весь план):
  1. PostgreSQL недоступен (нет psql/postgres/docker) → BLOCKED PG-части RQ-04/14/15/25 и любые schema-срезы. Условие разблокировки: disposable PostgreSQL 16 (или docker) с безопасным тестовым DSN.
  2. Redis недоступен + backend-зависимости не установлены → BLOCKED REAL_API-сценарии (S-03/S-13/S-21 REAL_API-части). Условие: disposable Redis + `python3 -m venv .venv && pip install -r backend/requirements.txt` по P0.
  3. PR #3114 активен (64 файла) → перед RQ-04/08/09/13/14/15/16/18/24 обязательна повторная сверка его head и файлов.
  4. D-01…D-07 OPEN — behavior-changing задачи ждут решений владельца.
- Status now: RQ-01 VERIFIED (в границах этого PR; DONE — после merge-сверки следующего цикла).
- Next smallest action: RQ-02 — direct_execute, first-touch `frontend/src/pages/registrar/registrarWorklistRows.ts` + его тест (оба вне #3114); исправить пусто-цифровую телефонную ветку поиска и ожидание теста, закрепляющего дефект; targeted Vitest + `git diff --check`.
- Checkpoint commit: см. PR из строки RQ-01; remote HEAD — сверять при продолжении.

### Шаблон следующей записи — скопировать и заполнить

```text
Evidence ID: E-NNN
Task / child:
UTC timestamp:
Agent / owner:
Repo branch:
Base SHA / tested HEAD:
Exact first-touch files:
Mode / gate command / result / generated handoff path:
Observed before:
Changed behavior:
Commands (working directory + literal command, without secrets):
Results (exit code, tests passed/failed/skipped):
Acceptance S-IDs / real API or mock / DB dialect:
Artifacts (repo-relative paths or CI URLs, no PHI):
Not checked and why:
PR URL / CI run / merge SHA when known:
Status now:
Blocker and exact release condition:
Next smallest action / exact next command:
Checkpoint commit / remote HEAD:
```

Не помещать чувствительные значения подключения в команды evidence. При невозможности отправить ветку явно записать LOCAL_ONLY и способ передачи без утверждения, что облако уже видит изменения.

## Восстановление после прерывания

1. Прочитать этот файл и свежие refs; проверить dirty files, branch и открытый PR.
2. Если есть IN_PROGRESS/IMPLEMENTED/VERIFIED/PR_OPEN — сначала сверить владельца и фактический diff. Не назначать себе чужую незавершенную работу без передачи.
3. Если журнал устарел относительно GitHub — восстановить факты из PR/commit/checks, отметить расхождение в E-NNN. Не запускать уже merged исправление повторно.
4. Если частично реализовано, сравнить с acceptance и продолжить недостающее; не переписывать готовую часть «с нуля».
5. Если нужен ответ D-ID, подготовить конкретное предложение. Пока ответа нет, выполнять только независимую авторизованную работу; активный незавершенный PR-цикл не обходить открытием нового.
6. Перед завершением сессии сохранить next action, ограничения, результаты и отправить checkpoint, если доступно. В чат достаточно task ID, статуса, ссылки на PR и следующего действия.

## Staging RQ-30

До фактической проверки все строки NOT_RUN. Это не препятствует отдельному завершению проверенного code PR, но запрещает объявлять всю систему проверенной/деплой завершенным.

| Проверка runbook | Статус | Evidence / blocker |
|---|---|---|
| Sentry frontend + backend delivery | NOT_RUN | — |
| DR: backup restores | NOT_RUN | — |
| AI feature kill-switch | NOT_RUN | — |
| AI safety contract | NOT_RUN | — |
| arq enqueue/process | NOT_RUN | — |
| Telegram delivery, если используется | NOT_RUN | — |
| PII scrubbing, 3 слоя | NOT_RUN | — |
| Pre-commit hooks | NOT_RUN | — |
| Backend unit suite | NOT_RUN | — |
| Frontend build + unit suite | NOT_RUN | — |
