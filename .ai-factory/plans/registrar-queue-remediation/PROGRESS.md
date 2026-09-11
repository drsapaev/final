# Журнал выполнения: регистратура и очереди

[Определения задач](../codex-registrar-queue-remediation-plan.md) · [Старт агента](CLOUD-START.md) · [Приемка](ACCEPTANCE.md)

Это единственный источник текущих статусов. Не вести отдельный конкурирующий чеклист в чате, issue или другой PLAN.md. Критерии задачи находятся в основном плане; история доказательств — здесь. Наличие отметки без проверяемого свидетельства не закрывает задачу.

## Точка продолжения

- Обновлено: 2026-09-11, RQ-06.a VERIFIED (runtime-PR этого среза открыт, merge сверить в следующем цикле); RQ-06 DONE (merged #3167, merge SHA `17b94ec4409e3dcc3578d4b53f6c084cf4dc676e`); RQ-01/RQ-02/RQ-03 DONE. Следующая минимальная незаблокированная задача — RQ-06.b (легаси-селекты category_id/doctor_id/currency той же формы) либо RQ-19 (frontend-only). RQ-04/RQ-05 — валидация требует disposable PostgreSQL (P0): без него backend-часть BLOCKED.
- План: v1; исходный main аудита: `22febf376f710a3b3b6ce57ac85de589ebba3f21`; актуальный проверенный базис: `8a548616523e48e00649b214729c69cf9f326fd4` (merged план #3157, RQ-01 #3159, RQ-02 #3160, docs-checkpoint #3162, RQ-03 #3163, docs #3164, payments #3166, RQ-06 #3167, docs #3168).
- Реализация: 4/30 закрыто (RQ-01, RQ-02, RQ-03, RQ-06 DONE); дочерний срез RQ-06.a VERIFIED в границах своего PR (детализация не повышает completion).
- Активная runtime-задача: RQ-06.a — PR открыт (ветка `codex/rq-06a-service-save-fields`, база `8a5486165`); merge сверить в следующем цикле.
- Подготовительный docs PR [#3157](https://github.com/drsapaev/final/pull/3157) **merged** в main (`be6012b18`); план доступен в fresh main — runtime-работа от fresh main разрешена.
- Следующий шаг: после merge RQ-06.a — сверить merge SHA, перевести RQ-06.a в DONE; далее RQ-06.b (легаси-селекты category_id/doctor_id/currency — тот же first-touch файл, отдельный узкий срез) либо RQ-19 (frontend-only, gate/direct по AGENTS; якоря Tabs/navigation — вне wizard-PR #3083-#3086). Перед backend-задачами (RQ-05 и др.) требуется disposable PostgreSQL — иначе BLOCKED по P0. Для RQ-04 дополнительно сверить head #3114.
- Дрейф F-05, зафиксированный RQ-06 (E-006): на базисе `1286ccbce` селектор queue_tag в ServiceForm вообще не доставлял значение тега (легаси `onChange` + `String(event)` → `'[object Object]'`), поэтому наблюдение аудита «profile.key записывается в department_key» через UI на текущем main не воспроизводится — дефект глубже; исправлены и проводка селекта (канонический `onValueChange`), и синхронизация (реальный `department_key` профиля). Обнаружены и зарегистрированы смежные дефекты той же формы: RQ-06.a, RQ-06.b.
- Дрейф плана, зафиксированный RQ-01: QD-2A (0055–0059) уже merged через PR #3093 (`1f775cb`), поэтому открытый PR #3077 выглядит дубликатом/суперсeded — не мержить без сверки содержимого; F-10/F-16 частично смягчены; F-14 частично изменен. Подробности в E-003.
- Открытые продуктовые решения: D-01…D-07 (все OPEN). Они не блокируют независимые fixes.
- Дрейф координации (RQ-03): открыты wizard-PR #3083/#3084/#3085/#3086/#3079 (Fix A/B/C/E/F) — трогают `AppointmentWizardV2.tsx` и хвост `wizardUtils.ts`, но НЕ блок фильтрации услуг (сверено по патчам, E-005). Перед следующим wizard-срезом — повторная сверка их head.
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
| RQ-01 | Актуальный базис | — | DONE | codex/rq-01-baseline-verification / [#3159](https://github.com/drsapaev/final/pull/3159) merged `84f561dff3f4d95b32e19cadc0a2c3b4f87ce2cb` | E-003 |
| RQ-02 | Поиск пациента | RQ-01 | DONE | codex/rq-02-registrar-search / [#3160](https://github.com/drsapaev/final/pull/3160) merged `11e6ab69d5921a4e667748d99de6131f5c2e65dc` | E-004 |
| RQ-03 | Услуги мастера | RQ-01 | DONE | codex/rq-03-wizard-services / [#3163](https://github.com/drsapaev/final/pull/3163) merged `2cf108cace3432690fb20843dfaa347c4b3ac121` | E-005 |
| RQ-04 | Атомарное отделение | RQ-01; проверить #3114 | TODO | — | — |
| RQ-05 | Обязательный врач | RQ-01 | TODO | — | — |
| RQ-06 | Профиль/тег/отделение | RQ-01 | DONE | codex/rq-06-profile-tag-department / [#3167](https://github.com/drsapaev/final/pull/3167) merged `17b94ec4409e3dcc3578d4b53f6c084cf4dc676e` | E-006 |
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
| RQ-06.a | handleConfirmSave парсит `formData.code` вместо `formData.price`/`category_id`/`doctor_id` (внесено f35b91d270, 2026-07-22): цена/категория/врач при сохранении формы обнуляются/теряются; исправить на корректные поля + regression-тест | RQ-06 | VERIFIED (PR_OPEN) | codex/rq-06a-service-save-fields / PR этого среза / E-007 |
| RQ-06.b | ServiceForm: селекты `category_id`/`doctor_id`/`currency` используют легаси `onChange` + `String(event)` → риск `'[object Object]'` в formData; runtime-проверка + миграция на канонический `onValueChange` (паттерн UserModal) + тесты | RQ-06 | TODO | обнаружен в RQ-06 (E-006, code-review того же паттерна); first-touch: `frontend/src/components/admin/ServiceCatalog.tsx` + соседний тест |

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
- Merge подтвержден (следующий цикл): PR #3159 squash-merged 2026-09-11, merge SHA `84f561dff3f4d95b32e19cadc0a2c3b4f87ce2cb`, все required checks на финальном head `193454461` success (PR Review Quality Gate перезапущен после приведения body к шаблону docs-only — первый прогон был FAIL по отсутствию обязательных секций, исправлено в том же PR). RQ-01 → DONE.
- Next smallest action: RQ-02 — direct_execute, first-touch `frontend/src/pages/registrar/registrarWorklistRows.ts` + его тест (оба вне #3114); исправить пусто-цифровую телефонную ветку поиска и ожидание теста, закрепляющего дефект; targeted Vitest + `git diff --check`.
- Checkpoint commit: см. PR из строки RQ-01; remote HEAD — сверять при продолжении.

### E-004 — RQ-02: исправлен поиск пациента (F-01)

- Task / child: RQ-02 (direct_execute — изменен только локальный фильтр отображения; gate не требуется по AGENTS для direct_execute).
- UTC timestamp: 2026-09-11, срез облачного агента.
- Repo branch: `codex/rq-02-registrar-search`; Base SHA / tested HEAD: `84f561dff3f4d95b32e19cadc0a2c3b4f87ce2cb` (fresh origin/main, включает merged RQ-01).
- Mode / gate: direct_execute (план: «если меняется только локальный фильтр»); pre-work block зафиксирован перед правками (mode/root cause/first-touch/allowed/denied/validation/stop). Опциональный gate-прогон с known-root-cause выполнен ранее в E-003 как валидация инструментария, в этом срезе не требовался.
- Exact first-touch files: `frontend/src/pages/registrar/registrarWorklistRows.ts`, `frontend/src/pages/registrar/__tests__/registrarWorklistRows.test.ts` (оба вне #3114, сверено в E-003).
- Observed before: буквенный запрос (кириллица/латиница) не фильтровал список: `searchDigits=''` → `phoneDigits.includes('') === true` → телефонная ветка пропускала каждую строку (ветка вкладки `registrarWorklistRows.ts:168-171` и агрегированный список `:237-241`); поведение было закреплено тестом «pre-existing quirk».
- Changed behavior: телефонная ветка поиска участвует только при непустых цифрах запроса (`searchDigits.length > 0 && …`) в обеих ветках (вкладка и «Все отделения»); буквенный запрос фильтрует по ФИО/ID/услугам; пустой запрос и цифровой/форматированный телефон ведут как раньше. Никаких серверных изменений, никаких новых полей пациента.
- Commands (working dir `/home/z/repo/frontend`):
  1. `node node_modules/vitest/vitest.mjs run src/pages/registrar/__tests__/registrarWorklistRows.test.ts --no-cache --reporter=dot` → **13/13 PASS** (включая новые RQ-02-проверки: пустой запрос возвращает исходный набор — обе ветки; кириллица «иван» находит только ФИО-совпадение; латиница «ivan» не возвращает все строки; форматированный телефон `+998 90 123-45-67` находит одну запись — обе ветки).
  2. Обязательный Tier 1 перед merge UI PR (docs/AGENTS_UI.md §13): `npm run test:run` → **219 files / 1871 tests PASS**; `npm run type-check` → EXIT=0; `npm run lint:check` → 0 errors (3082 pre-existing warnings); `npm run check-theme` → PASS; `npm run audit:icon-controls` → 0 new findings; `npm run build` → PASS (pre-existing chunk-size warnings).
  3. Self-contained Playwright suite (W0): `CI=1 npm run test:e2e -- e2e/registrar-time.spec.ts e2e/registrar-ux-audit.spec.ts e2e/cashier-ux-audit.spec.ts e2e/visual-regression.spec.ts e2e/frontend-10-route-smoke.spec.ts e2e/frontend-10-visual-a11y.spec.ts --project=chromium` → **82 passed** (5.2m; vite proxy noise — ожидаемый MOCK-уровень, backend не запущен).
  4. `git diff --check` → PASS. Локальный PR-review gate validator на body → PASS до push.
- Acceptance S-IDs: S-01 — частично покрыт (Vitest PASS на синтетических строках: кириллица, часть телефона, форматированный телефон, пустой запрос, обе ветки; browser MOCK — W0 suite 82 passed на MOCK-данных). REAL_API — NOT_RUN (нет disposable backend/Redis; уровень MOCK явно маркирован).
- Artifacts: изменения в этом PR (2 файла кода/теста + PROGRESS.md); no PHI (только синтетические ФИО/телефоны из фикстур теста).
- Not checked and why: REAL_API/browser-над-реальным-backend — нет disposable backend+PostgreSQL+Redis (частные blockers E-003); миграций/скрытых контрактов нет — не применимо.
- PR URL: см. строку RQ-02 реестра (PR этого среза); merge SHA — сверить в следующем цикле.
- Status now: RQ-02 VERIFIED (в границах этого PR; DONE — после merge-сверки).
- Merge подтвержден (сверка в отдельном docs-checkpoint): PR #3160 squash-merged 2026-09-11, merge SHA `11e6ab69d5921a4e667748d99de6131f5c2e65dc`; все required checks на head `1082d427` success (включая Frontend e2e). RQ-02 → DONE.
- Blocker: нет (только общие частные blockers E-003, не влияющие на этот срез).
- Next smallest action: после merge RQ-02 — сверить SHA; RQ-03 (gate): pre-work через `pwsh -NoProfile -File ./ai/langgraph/scripts/run_agent_gate.ps1 "RQ-03 …"` с известными якорями `frontend/src/components/wizard/wizardUtils.ts`; затем 3 воспроизведения из аудита.
- Checkpoint commit / remote HEAD: см. PR; remote — сверять при продолжении.

### E-005 — RQ-03: возвращены правильные услуги в мастер (F-02)

- Task / child: RQ-03 (режим gate — связь профилей и API-каталога; root cause подтвержден заранее, поэтому gate вызван с `--known-root-cause`).
- UTC timestamp: 2026-09-11, срез облачного агента.
- Repo branch: `codex/rq-03-wizard-services` (отдельный worktree `/home/z/final-rq03`, создан от fresh origin/main; базовый checkout не тронут). Base SHA / tested HEAD: `ec9633f50e8fa6e61f18e96f73e65ab8ebfdb28e` (= origin/main, включает merged RQ-01/RQ-02/docs-#3162).
- Mode / gate: `pwsh -NoProfile -File ./ai/langgraph/scripts/run_agent_gate.ps1 "RQ-03: …" --known-root-cause frontend/src/components/wizard/wizardUtils.ts` → `{"result":"gate_ok","mode":"execute","gate_misroute":false,"override_used":false,"first_touch_files":["frontend/src/components/wizard/wizardUtils.ts"]}`. Pre-work block (mode/anchor/first-touch/allowed/denied/validation/stop) зафиксирован в чате до правок.
- Exact first-touch files: `frontend/src/components/wizard/wizardUtils.ts`, `frontend/src/components/wizard/AppointmentWizardV2.tsx`, `frontend/src/components/wizard/__tests__/AppointmentWizardV2.contract.test.tsx`, новый соседний тест `frontend/src/components/wizard/__tests__/wizardServiceTabFilter.test.ts`, `PROGRESS.md` (checkpoint). Backend не менялся: поля `service.queue_tag`, `service.department_key`, `profile.queue_tags`, `profile.department_key` уже есть в текущем DTO (`_services_doctors.py` включает queue_tag; `/queues/profiles` возвращает department_key) — новый контракт не потребовался.
- Координация (сверка перед стартом): открытые PR #3083/#3084/#3085/#3086/#3079 (Fix A/B/C/E/F) трогают `AppointmentWizardV2.tsx` и (три из них) добавляют хелперы в КОНЕЦ `wizardUtils.ts`; патчи НЕ содержат `getWizardDepartmentFilterKeys|departmentFilter|availableServices` — блок фильтрации услуг не пересекается. #3114 — вне якорей RQ-03 (E-003). Зафиксировано в «Точке продолжения».
- Observed before (F-02): (1) `getWizardDepartmentFilterKeys(null)` → `['']`, потребитель фильтровал по `department_key ∈ {''}` → на «Все отделения» скрывалась каждая услуга с заполненным department_key; (2) теги профиля ecg `['ecg','echokg']` сравнивались с `department_key='cardiology'` услуги → ecg-услуга исчезала с вкладки ЭКГ (тег перепутан с отделением; в канонических данных `INITIAL_QUEUE_PROFILES` профиль ecg имеет `department_key: None`, поэтому сопоставление по отделению для ecg невозможно в принципе).
- Changed behavior: (1) вкладка «Все отделения» (null/''/'all') возвращает `null` из нового хелпера — каталог не ограничивается; (2) добавлен `getWizardServiceTabFilter(value, profiles)`: теги профиля сопоставляются с `service.queue_tag` (тег↔тег), `department_key` профиля — с `service.department_key` (отделение↔отделение); (3) неклассифицированные услуги (без отдела и тега) остаются видимыми на любой вкладке — прежнее поведение строк без department_key; (4) неизвестная вкладка/пустой профиль/деградированный режим без profiles-API сохраняют прежнее поведение по ключу (E-000: neurology → ожидаемая услуга). Edit-mode по-прежнему показывает все услуги. Легаси-экспорты `WIZARD_DEPARTMENT_FILTER_KEYS`/`getWizardDepartmentFilterKeys` сохранены для совместимости, мастером больше не используются. Поиск по услугам не затронут; выбор исполнителя не затронут (stop-условия соблюдены).
- Commands (working dir `/home/z/final-rq03/frontend`):
  1. `npm ci --legacy-peer-deps` → EXIT=0.
  2. `node node_modules/vitest/vitest.mjs run src/components/wizard/__tests__/wizardServiceTabFilter.test.ts src/components/wizard/__tests__/AppointmentWizardV2.contract.test.tsx --no-cache --reporter=dot` → **2 files / 25 tests PASS** (17 новых behavioral-тестов: 3 воспроизведения аудита + неизвестная/пустая/только-department профильные ветки + деградированный режим + регистронезависимость + совместимость легаси-хелпера; 8 обновленных contract-пинов).
  3. Обязательный Tier 1 (docs/AGENTS_UI.md §13): `npm run type-check` → EXIT=0; `npm run lint:check` → 0 errors (3081 pre-existing warnings); `npm run check-theme` → PASS; `npm run audit:icon-controls` → 0 new findings; `npm run build` → PASS (pre-existing chunk-size warnings); `npm run test:run` → **220 files / 1887 tests PASS** (29.7s).
  4. Self-contained Playwright suite (W0): `CI=1 npm run test:e2e -- e2e/registrar-time.spec.ts e2e/registrar-ux-audit.spec.ts e2e/cashier-ux-audit.spec.ts e2e/visual-regression.spec.ts e2e/frontend-10-route-smoke.spec.ts e2e/frontend-10-visual-a11y.spec.ts --project=chromium` → **82 passed** (5.2m; vite proxy noise — ожидаемый MOCK-уровень, backend не запущен).
  5. `git diff --check` → PASS (перед checkpoint-коммитом).
- Acceptance S-IDs: S-02 — покрыт Vitest-уровнем (helper-тесты на SYNTHETIC-профилях/услугах: «Все»/null, ecg+echokg против department=cardiology, custom/пустой профиль, неизвестная вкладка) + contract-пины + browser MOCK (W0 suite 82 passed на MOCK-данных). REAL_API/browser-над-реальным-backend — NOT_RUN (нет disposable backend/PostgreSQL/Redis; частные blockers E-003). Уровень доказательства: Helper + wizard contract + browser MOCK (соответствует колонке S-02 «Vitest + browser»).
- Artifacts: изменения в этом PR (3 измененных файла + 1 новый тест + PROGRESS.md); данные в тестах — SYNTHETIC (ключи/теги профилей, без PHI).
- Not checked and why: REAL_API/стенд с настоящим backend — среда без PostgreSQL/Redis (blocker E-003.2); миграций нет — не применимо; SQLite-проверки не требовались (frontend-срез).
- PR URL: [#3163](https://github.com/drsapaev/final/pull/3163) (head `d43d938882234e460db54e27bc56197812ae968a`); merge SHA — сверить в следующем цикле (статус VERIFIED/PR_OPEN до сверки).
- Status now: RQ-03 VERIFIED (в границах PR #3163).
- Merge подтвержден (этот docs-checkpoint): PR #3163 squash-merged 2026-09-11, merge SHA `2cf108cace3432690fb20843dfaa347c4b3ac121`; все required checks на финальном head `3007ae7791` success (Frontend lint/build/unit/e2e, PR Review Quality Gate, PR Required Gate, Regression Audit Gate, CodeQL, security scans). RQ-03 → DONE.
- Blocker: нет (частные blockers E-003 не затрагивают этот срез).
- Next smallest action: после merge RQ-03 — сверить merge SHA и перевести RQ-03 в DONE; затем RQ-05 (gate, OpenAPI review; first-touch `backend/tests/integration/test_registrar_services_grouping.py`, serializer-ветка; `_services_doctors.py` вне #3114 — сверить перед стартом) или RQ-19 при продолжении блокировок.
- Checkpoint commit / remote HEAD: см. PR этого среза; remote — сверять при продолжении.

### E-006 — RQ-06: профиль/тег/отделение услуги в ServiceCatalog (F-05)

- Task / child: RQ-06 (режим gate; root cause подтвержден заранее — `--known-root-cause`).
- UTC timestamp: 2026-09-11, срез облачного агента.
- Repo branch: `codex/rq-06-profile-tag-department` (отдельный worktree `/home/z/final-rq06` от fresh origin/main; базовый checkout не тронут). Base SHA / tested HEAD: `1286ccbce7ddeb0c63c99c709325d6a37913d984` (= origin/main, включает merged RQ-03/docs #3164 и payments #3166).
- Mode / gate: `pwsh -NoProfile -File ./ai/langgraph/scripts/run_agent_gate.ps1 "RQ-06: …" --known-root-cause frontend/src/components/admin/ServiceCatalog.tsx` → `{"result":"narrow_override","mode":"execute","handoff_required":false,"gate_misroute":false,"override_used":true,"known_root_cause":"frontend/src/components/admin/ServiceCatalog.tsx","first_touch_files":["frontend/src/components/admin/ServiceCatalog.tsx"]}`. Pre-work block (mode/anchor/first-touch/allowed/denied/validation/stop) зафиксирован до правок.
- Координация: открытые PR проверены по файлам (GitHub API): #3114 (64 файла) НЕ трогает `ServiceCatalog.tsx` (из admin — только `QueueCabinetManagement.tsx`); wizard-PR #3083/#3084/#3085/#3086/#3079 и dependabot-PR — без пересечений с якорями RQ-06.
- Observed before (F-05 дрейф на `1286ccbce`): (1) селектор «Вкладка регистратуры» в ServiceForm предлагает только `profile.queue_tags?.[0] || profile.key` — второй+ теги профиля недостижимы; (2) синхронизация `handleChange('queue_tag')` писала в `department_key` значение `profile.key` вместо контрактного `profile.department_key` (`backend/app/api/v1/endpoints/registrar_integration/_queue_profiles.py`: `queue_tags` и `department_key` — разные поля); (3) НАЙДЕН ДРЕЙФ: сам Select использует легаси `onChange={(value) => handleChange('queue_tag', String(value))}`, а канонический Select (`ui/macos/Select.tsx`) в legacy-режиме шлёт event-объект → в formData попадало `'[object Object]'`, т.е. на текущем main выбор тега через UI вообще не доставлял значение (аудит-наблюдение «profile.key записывается» через UI не воспроизводится — дефект глубже).
- Changed behavior: (1) новый экспортируемый хелпер `buildQueueTagOptions(profiles)`: по одной осмысленной опции на КАЖДЫЙ разрешенный тег активного профиля (мульти-тег — подпись «title · tag»), легаси-fallback на `profile.key` для профилей без тегов, неактивные профили исключены, дедупликация общего тега (первый активный профиль), `department_key` переносится из контракта профиля отдельным полем опции; (2) синхронизация пишет реальный `profile.department_key`; при отсутствии `department_key` — явная пустота (на сервер уходит `null`), никакой выдумки отдела из ключа профиля; (3) селектор очереди переведен на канонический `onValueChange` (паттерн UserModal) — значение тега реально доставляется в formData; (4) `QueueProfileItem` дополнен контрактным полем `department_key`. Backend/DTO не менялись (существующий контракт сохранен); поиск/категории/врачебные селекты формы не тронуты (см. RQ-06.a/RQ-06.b — зарегистрированы, не чинились «заодно»).
- Commands (working dir `/home/z/final-rq06/frontend`):
  1. `npm ci --legacy-peer-deps` → EXIT=0.
  2. `node node_modules/vitest/vitest.mjs run src/components/admin/__tests__/ServiceCatalog.profileTags.test.tsx --no-cache` → **8/8 PASS** (5 unit-тестов хелпера: мульти-тег/произвольный ключ/отсутствие department_key/неактивные/дедупликация; 3 integration: сохранение второго тега мульти-тег-профиля дает `department_key=cardiology`, а НЕ `synthetic-diagnostics`; профиль без department_key дает `department_key=null`; легаси-fallback дает `queue_tag=legacy-procedures, department_key=procedures`).
  3. Соседи: `ServiceCatalog.emptyState + Admin.i18n.contract + AdminRemaining.i18n.contract` → **3 files / 44 tests PASS**.
  4. Обязательный Tier 1 (docs/AGENTS_UI.md §13): `npm run type-check` → EXIT=0; `npm run lint:check` → 0 errors (3081 pre-existing warnings); `npm run check-theme` → PASS; `npm run audit:icon-controls` → 0 new findings; `npm run build` → PASS (pre-existing chunk-size warnings); `npm run test:run` → **221 files / 1908 tests PASS** (30.7s).
  5. Self-contained Playwright suite (W0): `CI=1 npm run test:e2e -- e2e/registrar-time.spec.ts e2e/registrar-ux-audit.spec.ts e2e/cashier-ux-audit.spec.ts e2e/visual-regression.spec.ts e2e/frontend-10-route-smoke.spec.ts e2e/frontend-10-visual-a11y.spec.ts --project=chromium` → **82 passed** (5.2m; MOCK).
  6. `git diff --check` → PASS.
- Acceptance S-IDs: S-04 — покрыт Vitest-уровнем (unit хелпера + integration сохранения: профиль `key=synthetic-diagnostics`, `department_key=cardiology`, два тега — точка сценария; отсутствие department_key обрабатывается явно; payload сохранения содержит ровно контрактные поля) + browser MOCK (W0 82 passed). REAL_API/browser-над-реальным-backend — NOT_RUN (нет disposable backend/PostgreSQL/Redis; частные blockers E-003). Серверная валидация существующего контракта не менялась (backend не тронут).
- Artifacts: PR этого среза (1 измененный файл + 1 новый тест + PROGRESS.md); данные SYNTHETIC (ключи профилей/теги — доменные идентификаторы, без PHI).
- Not checked and why: REAL_API — среда без PostgreSQL/Redis (blocker E-003.2); SQLite не применим (frontend-срез); screenshots S-04 — только MOCK-уровень.
- Discovered defects (зарегистрированы, НЕ чинились в этом срезе): **RQ-06.a** — `handleConfirmSave` парсит `formData.code` вместо `formData.price`/`category_id`/`doctor_id` (blame `f35b91d270`, 2026-07-22): `price` → `parseFloat(code)` = NaN → null и т.п.; **RQ-06.b** — селекты `category_id`/`doctor_id`/`currency` ServiceForm используют тот же легаси `onChange`+`String(event)` паттерн (code-review; runtime-пруф пока только для queue_tag).
- PR URL: [#3167](https://github.com/drsapaev/final/pull/3167) (head `a5579a4f223da48801c0bc87d6812af066a6ceb9`); merge SHA — сверить в следующем цикле (статус PR_OPEN/VERIFIED до сверки).
- Status now: RQ-06 VERIFIED (в границах PR #3167).
- Merge подтвержден (этот docs-checkpoint): PR #3167 squash-merged 2026-09-11, merge SHA `17b94ec4409e3dcc3578d4b53f6c084cf4dc676e`; все required checks на финальном head `faad4e711` success (37/37, включая Frontend e2e и PR Required Gate). RQ-06 → DONE.
- Blocker: нет (частные blockers E-003 не затрагивают этот срез).
- Next smallest action: после merge — сверить merge SHA, перевести RQ-06 в DONE; затем RQ-06.a (narrow, direct_execute/gate по AGENTS; тот же first-touch файл) либо RQ-19 при приоритете frontend-only.
- Checkpoint commit / remote HEAD: см. PR этого среза; remote — сверять при продолжении.

### E-007 — RQ-06.a: сохранение полей формы услуги (price/category/doctor/duration)

- Task / child: RQ-06.a (дочерний срез RQ-06; режим gate_known_root_cause — сохранение формы формирует backend-payload услуги; root cause подтвержден в E-006 и перепроверен на актуальном main).
- UTC timestamp: 2026-09-11, срез облачного агента.
- Repo branch: `codex/rq-06a-service-save-fields` (отдельный worktree `/home/z/final-rq06a` от fresh origin/main; базовый checkout не тронут). Base SHA / tested HEAD: `8a548616523e48e00649b214729c69cf9f326fd4` (= origin/main, включает merged RQ-06 #3167 и docs #3168).
- Mode / gate: `pwsh -NoProfile -File ./ai/langgraph/scripts/run_agent_gate.ps1 "RQ-06.a: …" --known-root-cause frontend/src/components/admin/ServiceCatalog.tsx` → `{"result":"narrow_override","mode":"execute","gate_misroute":false,"override_used":true,"first_touch_files":["frontend/src/components/admin/ServiceCatalog.tsx"]}`. Pre-work block (mode/anchor/first-touch/allowed/denied/validation/stop) зафиксирован до правок.
- Координация (сверка перед стартом, GitHub API): открытые PR #3114 (head обновился на `183898a867eb`), #3042, #3089, #3046, wizard-PR #3083/#3084/#3085/#3086/#3079, #3102, #3155 — НИ ОДИН не трогает `ServiceCatalog.tsx`/ServiceForm (проверено по файлам каждого PR).
- Observed before (воспроизведено тестом на дефектном коде): inline ServiceForm в `ServiceCatalog.tsx` (handleConfirmSave, строки ~994–1006) парсил `formData.code` для ВСЕХ числовых полей: `price: formData.price ? parseFloat(String(formData.code ?? '')) : null` и аналогично `category_id`/`doctor_id`/`duration_minutes`. Фактический payload (зафиксирован падающим тестом): `price: NaN` (→ null в JSON), `duration_minutes: 30` независимо от ввода, `category_id: null`, `doctor_id: null` — при введенных пользователем цене 50000 и длительности 45. Т.е. каждое сохранение через UI молча теряло цену/категорию/врача и сбрасывало длительность. Эталон корректного парсинга существует в standalone `ServiceForm.tsx:227-230` (файл вне импортов, использован как reference-only). Blame: аннотация `Record<string, unknown>` поверх дефектных строк — `86850cf48` (2026-07-29, BS-66).
- Changed behavior: `handleConfirmSave` парсит каждое поле из собственного значения formData: `price` → `parseFloat(String(formData.price))`; `category_id`/`doctor_id` → `parseInt(String(...), 10)`; `duration_minutes` → `parseInt(String(formData.duration_minutes ?? ''), 10) || 30` (прежний дефолт 30 сохранен). Семантика пустых значений не изменена: пустая цена/категория/врач → явный `null`. Backend/DTO не затронуты; селекты `category_id`/`doctor_id`/`currency` сознательно НЕ тронуты (это зарегистрированный отдельный срез RQ-06.b — delivery-дефект, а не parsing); preview-модалка, код-валидации и Rest формы не менялись.
- Commands (working dir `/home/z/final-rq06a/frontend`):
  1. `npm ci --legacy-peer-deps` → EXIT=0.
  2. Fail-first: новый `node node_modules/vitest/vitest.mjs run src/components/admin/__tests__/ServiceCatalog.saveFields.test.tsx --no-cache` на дефектном коде → 2 failed / 1 passed (edit: ожидание 65000/3/7/45 против фактических NaN/null/null/30; new: NaN/30 вместо 50000/45; воспроизведение зафиксировано в логе среза).
  3. После фикса: тот же файл → **3/3 PASS** (edit-режим с preview-подтверждением: payload `price:65000, category_id:3, doctor_id:7, duration_minutes:45`; new-режим: `price:50000, duration_minutes:45, category_id:null, doctor_id:null`; явные null для нетронутых полей, `price` не NaN).
  4. Соседи: `ServiceCatalog.profileTags + ServiceCatalog.emptyState + AdminRemaining.i18n.contract` → **3 files / 42 tests PASS**.
  5. Обязательный Tier 1 (docs/AGENTS_UI.md §13): `npm run type-check` → EXIT=0; `npm run lint:check` → 0 errors (3081 pre-existing warnings); `npm run check-theme` → PASS; `npm run audit:icon-controls` → 0 new findings; `npm run build` → PASS (pre-existing chunk-size warnings); `npm run test:run` → **222 files / 1911 tests PASS** (33.2s; +1 файл/+3 теста этого среза).
  6. Self-contained Playwright suite (W0): `CI=1 npm run test:e2e -- e2e/registrar-time.spec.ts e2e/registrar-ux-audit.spec.ts e2e/cashier-ux-audit.spec.ts e2e/visual-regression.spec.ts e2e/frontend-10-route-smoke.spec.ts e2e/frontend-10-visual-a11y.spec.ts --project=chromium` → **82 passed** (5.3m; vite proxy noise — ожидаемый MOCK-уровень, backend не запущен).
  7. `git diff --check` → PASS (перед checkpoint-коммитом).
- Acceptance S-IDs: S-04 — частично усилен (поле сохранения услуги: значения формы доходят до payload сохранения без искажений на SYNTHETIC-фикстурах; Vitest-уровень). Полный S-04 (REAL_API сохранение и повторное чтение) — NOT_RUN (нет disposable backend/PostgreSQL/Redis; частные blockers E-003). Browser MOCK — W0 82 passed.
- Artifacts: PR этого среза (1 измененный файл + 1 новый тест + PROGRESS.md); данные SYNTHETIC («Синтетическая …» — доменные фикстуры, без PHI).
- Not checked and why: REAL_API — среда без PostgreSQL/Redis (blocker E-003.2); серверная валидация контракта не менялась (backend не тронут); standalone `ServiceForm.tsx` не модифицировался (вне импортов, reference-only — в границах first-touch не входит).
- PR URL: PR этого среза (ветка `codex/rq-06a-service-save-fields`); merge SHA — сверить в следующем цикле (статус VERIFIED/PR_OPEN до сверки).
- Status now: RQ-06.a VERIFIED (в границах этого PR).
- Blocker: нет (частные blockers E-003 не затрагивают этот срез).
- Next smallest action: после merge — сверить merge SHA, перевести RQ-06.a в DONE; затем RQ-06.b (легаси-селекты category_id/doctor_id/currency → канонический `onValueChange`, тот же first-touch файл, отдельный узкий PR) либо RQ-19.
- Checkpoint commit / remote HEAD: см. PR этого среза; remote — сверять при продолжении.

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
