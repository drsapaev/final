# План трека NURSE-V2: человек-медсестра, не-врачебное клиническое обслуживание

Создан: 2026-09-18. Версия плана: 2 (коррекции merge-checklist владельца 2026-09-18: нумерация миграций, service-level execution, ownership-маппинг, Nurse role enum, статус QD-2/RQ-15).
Статус: **APPROVED — план принят владельцем (merge-checklist 2026-09-18 закрыт). Design-GO на N2-2 ПОЛУЧЕН 2026-09-19 (D1/D2/D3 FINAL — раздел «N2-2 design-GO (FINAL)» ниже): runtime-работа N2-2 разрешена в границах среза; serving API (N2-3) и tablet (N2-5) — отдельные гейты. Ничего не deploy автоматически.**
Основание: решение владельца о приоритетной корректировке (IM-сессия `web-dff6f17a-e319-45e3-a564-42a853cd3f0e`, channel `zai-web`, trace `1a0b0a46d285c559`, 2026-09-18). Коррекции версии 2: merge-checklist владельца (комментарий к PR #3322, 2026-09-18T16:45Z) + вердикт владельца по docs-PR #3326 (trace `1a0b5807929665e5`, 2026-09-19: route «merge #3322 first, потом #3326 после fresh sync»). Дословные ключевые директивы:

> «Наш следующий продуктовый приоритет — NURSE V2.»
> «Записать следующий новый track: NURSE-V2 — human non-doctor clinical serving»
> «Canonical role: Nurse»
> «Не менять исторические N-3 записи: старый Nurse был правильно retired. Новый Nurse v2 — новая product capability.»
> «Не переаудировать всю систему ролей. Не делать public.roles cleanup предварительным условием.»
> «После #3315 не брать автоматически RQ-17/RQ-18/RQ-26 или другие старые queue backlog slices. Если следующий старый RQ не является P0/P1 blocker для Nurse: DEFER.»
> «После этого STOP для design-GO. Ничего не merge/deploy автоматически.»

**Точка входа агента после design-GO:** этот файл + журнал трека (раздел «Текущее состояние» ниже). Журнал трека registrar-queue-remediation для NURSE-V2 НЕ ведётся — это отдельный трек.

Документ не означает, что перечисленное уже реализовано. Наличие плана не разрешает деплой, изменение production-данных или принятие открытых продуктовых решений без владельца.

## Settings

- Testing: yes — контрактные, RBAC-негативные (deny-by-default) и обязательные PG-concurrency проверки на каждом срезе.
- Logging: minimal — без ФИО, телефона, диагноза, токенов и полного тела запросов.
- Docs: yes — после каждого среза запись в раздел «Текущее состояние» с PR/commit/командами/результатами/следующим шагом.
- Roadmap linkage: новая продуктовая capability; отдельна от registrar-queue-remediation и от VPS-промоушена.
- Стек: FastAPI / SQLAlchemy / PostgreSQL / Alembic; React 19 / TypeScript / Vite.
- Обычные порты: backend 18000, frontend 5173, staging PostgreSQL 55432. Номер порта не доказывает, что среда тестовая.

## Цель и границы

Медсестра (Nurse) — человеческая учётная запись (`User` с канонической ролью `Nurse`), которая обслуживает назначенную ей очередь на рабочем месте/кабинете: видит ожидающих, вызывает следующего, начинает обслуживание, выполняет конкретную услугу, отмечает no-show и incomplete. Nurse — не врач и не регистратор: не подписывает врачебную EMR, не ставит диагноз, не управляет пользователями, не касается финансов, не обслуживает чужие очереди и не закрывает весь визит только потому, что выполнена одна процедура.

**Различать сущности (продуктовый контракт владельца):**

- **Nurse User = кто работает.** Учётная запись с ролью Nurse; все операции атрибутируются реальному User (`called_by_user_id` / `served_by_user_id`).
- **QueueResource = какую очередь/кабинет обслуживают.** Справочник-исполнитель без врача (`backend/app/models/online_queue.py:85-127`): «НЕ аккаунт: логина/RBAC-роли у него нет и не будет» (докстринг модели). Никогда не становится человеческим аккаунтом.

**Запрещённые суррогаты (по решению владельца):** Nurse → Doctor alias; ProcedureStaff; Technician вместо Nurse; Registrar/Admin для обхода permissions; Resource как человеческий аккаунт.

**Историческая честность N-3:** старая роль Nurse была корректно удалена (production census 2026-09-05 = 0 строк; `RETIRED_ROLE_SPELLINGS` — `backend/app/core/roles.py:85`). NURSE-V2 — новая capability: ввод роли осознанно амендирует retirement-гварды и пины (`test_nurse_retirement.py`), НЕ переписывая исторические записи о самом решении N-3.

## Переиспользуемые поверхности (discovery 2026-09-18, всё уже существует)

Ничего из перечисленного не переизобретать; новый код только назначает и авторизует:

- **QueueResource** — `backend/app/models/online_queue.py:85-127`: `queue_tag` (точное совпадение с `DailyQueue.queue_tag`), `display_name`, `active`, `default_cabinet`, `start_number_online`, `max_online_per_day`.
- **DailyQueue** — `online_queue.py:130-230`: owner-XOR (`specialist_id` XOR `queue_resource_id`), `cabinet_number/floor/building`, day-снапшот `start_number` (0067), `active`, `opened_at`.
- **OnlineQueueEntry** — `online_queue.py:233-380`: статус-машина `waiting → called → in_service/in_progress → served | incomplete | no_show | cancelled` (терминальный набор — `telegram_webhook/_helpers.py:1003`); атрибуция оператора QF-1 (миграция 0054): `called_by_user_id`, `served_by_user_id`, `served_at` — принимает ЛЮБОЙ user id, роль-агностична; `priority` (0/1/2); `(queue_id, number)` UNIQUE DEFERRABLE (0065).
- **Call-next локинг/state-machine** — `QRQueueService.call_next_patient` (`backend/app/services/qr_queue/_queue_ops.py:115-280`): детерминированный выбор очереди + `.with_for_update()` на waiting-кандидате (`priority DESC, coalesce(queue_time, created_at) ASC, id ASC`); нумерация `get_next_queue_number` держит `FOR UPDATE` на строке DailyQueue (`queue_svc/_operations.py:685-761`).
- **Действующие эндпоинты очередей (паттерн + точка расширения):** REST call-next `POST /api/v1/queue/{specialist_id}/call-next` (`qr_queue/_queue_ops.py:41-266`); doctor-panel call/start/complete (`doctor_integration/_queue_ops.py:425-589 / 592-723 / 726-1000+`; установка `served_by_user_id`/`served_at` — L897-906); no-show/incomplete/restore (`qr_queue/_entries.py:95-167 / 220-268 / 16-92`). Ключевой факт: на resource-принадлежных очередях (specialist IS NULL) call/start/complete сейчас **Admin-only** (`_queue_ops.py:470-485, 627-644, 879-885`) — NURSE-V2 расширяет эту политику на назначенную Nurse, не меняя owner-модель.
- **Ролевая модель:** `users.role` строка-SSOT (`models/user.py:44`); гейт `require_roles(...)` (`core/security.py:112-182`); `UserRole.from_string` (`core/rbac.py`); write-словарь `_USER_MANAGEMENT_ROLE_PATTERN` (`schemas/user_management.py`); permission-сеты `StaffAuthorizationService` (`services/authorization/staff.py:139-174`).
- **EMR-граница (денайл «бесплатный»):** `EMR_V2_WRITE_ROLES` + `ensure_emr_visit_access` (`emr_v2.py:68-138`) уже 403 для любой роли без активного Doctor-профиля — Nurse не добавлять в grant-листы, и отрицание работает без нового кода.
- **Visit-граница:** `VisitLifecycleService` (`visit_lifecycle_service.py:85-478`): `complete_visit` не требует EMR-подписи; `close_visit` (`L457`, терминал «EMR signed + payment») остаётся врачебным/кассирским/админским — Nurse не закрывает визит.
- **Frontend:** React 19 + Vite; `routeRegistry.ts` (`ROUTE_REGISTRY`, `SIDEBAR_PRESETS`) + `App.tsx` `ROUTE_COMPONENTS`; паттерн зеркала — `DoctorPanel.tsx` + `components/doctor/DoctorQueuePanel.tsx`; i18n `ru` default (+uz-Latn/uz-Cyrl/en/kk).
- **Миграции:** следующая ревизия — **next available Alembic revision от fresh origin/main; номер не резервируется заранее** (текущий head `0069_sentinel_pair_retirement`). Перед каждым migration PR: fetch + rebase на fresh main; `alembic heads` — ровно один head; сверка: fresh main == alembic_version production.
- **PG-concurrency паттерны тестов:** двухсоединечные `threading.Barrier` (`test_rq14a1_numbering_integrity_pg.py:402-424`); scratch-БД + `alembic upgrade head` (`test_rq14_qr_desk_owner_consistency_pg.py:131-146`).

## Минимальная модель назначения (design-цель, финализируется на design-gate N2-2)

`Nurse User → allowed QueueResource / workplace → cabinet/station → active assignment`.

Сегодня связи nurse↔resource нет вовсе (greenfield). Предложение: одна новая таблица назначения (рабочее имя `nurse_workplace_assignments`, отдельная миграция — номер по правилу «Миграции» выше): `user_id FK users.id`, `queue_resource_id FK queue_resources.id`, `cabinet/station` (по умолчанию — `QueueResource.default_cabinet`, переопределяемо), `is_active`, временные метки; инвариант — partial `UNIQUE(user_id, queue_resource_id) WHERE is_active`; явное решение «одно активное назначение или несколько» фиксируется на design-gate N2-2; inactive-назначения = исторические записи (не drift); QueueResource остаётся справочником без логина. Никаких человеческих полей в QueueResource не добавлять.

## N2-2 фиксации по merge-checklist владельца (2026-09-18)

Решения ниже зафиксированы ДО старта N2-2 по merge-checklist владельца (комментарий к PR #3322, 2026-09-18); раздел — SSOT-перенос директив, формулировки владельца сохранены дословно, где возможно.

- **Nurse role — enum-решение (одна строка):** re-open retired-значения — каноническая роль `Nurse` возвращается в ролевую модель (дешевле миграционно: `users.role` — строка-SSOT, без нового enum-значения и без ALTER TYPE); `test_nurse_retirement.py` и retirement-гварды переосмысляются как «старые N-3 поверхности закрыты» (вместо «Nurse не существует»); исторические записи N-3 не переписываются.
- **Service-level execution (модель по умолчанию + узкий gate):** `VisitService` + status (pending / in_progress / completed / incomplete / cancelled) + `started_at` + `completed_at` + `performed_by_user_id` → `users.id`, либо child-table `ServiceExecution` — по результату gate. Gate узкий, без общего аудита: read-only inventory — только существование `VisitService.qty > 1` (negative evidence); решения по сеансам/исполнителям/повторам — от domain-источника (сверка с владельцем клинического workflow): текущая схема эти факты не записывает, «нет данных» ≠ «нет потребности»; зафиксировать escalation trigger — какое наблюдение переводит модель на ServiceExecution. STOP для human-GO — только на решении VisitService vs ServiceExecution.
- **Ownership-маппинг (правило принадлежности услуг станции):** правило — таблица соответствия (не поле каталога): `queue_resource_services` (`queue_resource_id` ↔ `service_id`, `is_active`) — услуга визита принадлежит данной станции / queue-resource ⟺ существует активная строка соответствия. Таблица соответствия выбрана потому, что услуга может обслуживаться более чем на одной станции (M:N), а QueueResource остаётся справочником без человеческих полей (контракт владельца). Без этого правила «QueueEntry → served только после завершения всех услуг станции» невычислимо; с ним — entry разрешено флипать в served, когда все услуги визита, привязанные к станции активными строками соответствия, достигли терминального статуса по service-level модели выше. Финальная сверка правила с владельцем клинического workflow — в design-gate N2-2.

## N2-2 design-GO (FINAL, владелец 2026-09-19)

Три решения владельца, данные после preflight и design-материалов агента (fresh main `aecf739aa`, единственный Alembic head `0070_lab_results_lineage`, production-on-record 0069 → main впереди на 0070):

- **D1 FINAL — ServiceExecution, НЕ расширение VisitService.** Отдельная сущность: `visit_service_id` FK; `queue_entry_id` FK nullable (для Nurse-serving API N2-3 — обязателен); `attempt_no`; `status` (in_progress | completed | incomplete | cancelled); `started_by_user_id` + `started_at`; `performed_by_user_id` + `completed_at`; `incomplete_reason`; `created_at`/`updated_at`. Повтор после incomplete = НОВЫЙ attempt, история не перезаписывается. Число executions НЕ выводится автоматически из `VisitService.qty` (qty — коммерческая строка). DB-инвариант: не более одного одновременно активного (in_progress) execution на VisitService. `no_show` остаётся queue-level состоянием. Обоснование: qty>1 достижим; нужна история incomplete→retry; услугу может начать одна медсестра, закончить другая; нужна идемпотентность исполнения; «выполнить услугу» ≠ «закрыть Visit».
- **D2 FINAL — несколько активных назначений.** Одна Nurse → несколько QueueResource; один QueueResource → несколько Nurse; инвариант: не более одного ACTIVE назначения на пару (user_id, queue_resource_id) — partial `UNIQUE ... WHERE is_active`. Кабинет хранится в assignment как override; NULL → `QueueResource.default_cabinet`. Ограничение «одна активная очередь на Nurse вообще» НЕ вводится (tablet позже выбирает контекст; сменная модель — отдельная session/shift capability, не RBAC).
- **D3 FINAL — `queue_resource_services` НЕ создаётся.** Канонический роутинг остаётся существующим QD-2 SSOT: `Service.queue_tag == QueueResource.queue_tag` (+ `requires_doctor=false` для resource-serving). Второй SSOT-маппинг не заводится без доказанного бизнес-кейса (один queue_tag, но разные service-подмножества на разных ресурсах — если появится, это отдельное design-решение).

RBAC-контракт N2-2: `Roles.NURSE = "Nurse"` возвращается; `'nurse'` убирается из `RETIRED_ROLE_SPELLINGS`; история N-3 НЕ переписывается; старые grants НЕ возвращаются — Nurse может иметь аккаунт/логиниться/иметь назначения, но НЕ получает Doctor/Registrar/EMR/финансы/admin/staff-гранты; serving-permissions — только в N2-3, строго через активное назначение. Не менять public.roles как prerequisite. QD-2/RQ-15 не трогать (FROZEN/DONE). Миграции — от актуального fresh-main head (номер не резервируется; на момент GO — next available 0071); ничего не deploy.

## Срезы (предполагаемые PR boundaries)

| Срез | Содержание | Затрагиваемые поверхности | Gate |
|---|---|---|---|
| N2-1 | Этот план (track definition + discovery) | только docs | **design-GO владельца** — получен через merge-checklist 2026-09-18 (merge плана после закрытия пунктов) |
| N2-2 | Роль Nurse + модель назначения | отдельная миграция (номер — next available от fresh main); `core/roles.py`, `core/rbac.py`, `StaffAuthorizationService`, `_USER_MANAGEMENT_ROLE_PATTERN`, `user_mgmt` (создание/назначение), admin-эндпоинты назначения; амендация retirement-пинов (`test_nurse_retirement.py` — история N-3 сохраняется); frontend `BackendRole` union + parity-тесты | PR отдельно; owner review |
| N2-3 | Nurse serving API в назначенной очереди: list waiting / call-next / start / complete-service / no-show / incomplete | новые nurse-эндпоинты или расширение существующих (`qr_queue`, `doctor_integration` паттерны); переиспользование call-next локинга; атрибуция `called_by_user_id`/`served_by_user_id` реальному User; авторизация строго по активному назначению | PR отдельно; owner review |
| N2-4 | Обязательный PG concurrency-proof (сценарий владельца §6 ниже) — acceptance-сьют среза N2-3 (или отдельный PR, границу зафиксирует design-GO) | PG-тесты по паттернам rq14a1/rq16c | PR; owner review |
| N2-5 | Минимальная tablet-поверхность (после backend-фундамента) | `frontend/src/pages/` (новая страница), `routeRegistry.ts`, `App.tsx`, `types/roles.ts`; НЕ большая клиническая панель | PR отдельно; owner review |

Каждый срез начинается с показа владельцу: цель, first-touch файлы, проверки, stop conditions. Ничего не merge/deploy автоматически.

## Acceptance criteria (контракт владельца, дословно)

**Backend (§5):** Nurse со своего аккаунта может только в назначенной очереди:

- увидеть ожидающих;
- вызвать следующего;
- начать обслуживание;
- выполнить конкретную услугу;
- отметить no-show;
- отметить incomplete.

Запрещено по умолчанию:

- подписывать врачебную EMR;
- выставлять диагноз;
- управлять пользователями;
- финансы;
- чужие очереди;
- закрывать весь visit только потому, что выполнена одна процедура.

Все операции атрибутируются реальному User.

**Concurrency (§6, обязательный PostgreSQL-сценарий):** две Nurse, один QueueResource procedures, два кабинета, одновременный call-next. Доказать:

- один QueueEntry не выдаётся двум Nurse;
- каждая получает отдельного пациента;
- повтор запроса идемпотентен;
- `served_by_user_id` = фактическая Nurse;
- reconnect/reload не теряет активное обслуживание.

**Tablet UI (§7, после backend-фундамента):** отдельная минимальная поверхность; не большая клиническая панель. Экран содержит: кабинет/рабочее место; текущий пациент; ожидающие; кнопки «Вызвать следующего», «Начать», «Выполнено», «Не явился», «Не завершено».

## Не-цели (out of scope)

- Пере-аудит всей системы ролей; **public.roles cleanup НЕ является предусловием** (таблица де-факто мертва, mounted-but-unused).
- EMR, диагностика, финансы, управление пользователями для Nurse.
- Большая клиническая панель вместо минимальной tablet-поверхности.
- Старые RQ-срезы (RQ-17/RQ-18/RQ-26 и др.) — DEFER, если не P0/P1-блокер для Nurse.
- Изменение исторических N-3 записей.

## STOP discipline

- До design-gate N2-2 — никакой runtime-работы по этому треку (track-level GO получен через merge-checklist 2026-09-18; runtime открывается только после design-gate N2-2).
- После #3315 старые RQ-задачи автоматически не брать; если следующий старый RQ не P0/P1-блокер для Nurse — DEFER.
- QD-2/RQ-15 — FROZEN / DONE с 2026-09-18 (0069 применена на production и VERIFIED владельцем); новые QD-2 hardening PR — только по production incident или доказанному P0/P1.

## После merge — старт N2-2 (директива владельца, 2026-09-18)

1. Preflight: fetch + rebase fresh origin/main; `alembic heads` = single head; fresh main == alembic_version production.
2. N2-2 scope: enum-решение из раздела «N2-2 фиксации» (re-open); NurseWorkplaceAssignment — partial `UNIQUE(user_id, queue_resource_id) WHERE is_active`, явное решение «одно активное назначение или несколько», inactive-назначения = исторические записи (не drift); service execution model по gate из раздела «N2-2 фиксации».
3. STOP для human-GO — только на решении VisitService vs ServiceExecution.
4. Не переаудировать Visit/EMR. Не трогать EMR/финансы/Doctor-алиасы. Runtime-код до design-gate N2-2 не писать.
5. Ничего не deploy автоматически.

## N2-3 brief (зафиксировано владельцем 2026-09-18; не merge-blocking, не потерять)

- матрица переходов status + кто триггерит каждый; эффект no-show на sibling-pending услуги;
- updated_at/updated_by или append-only лог переходов (billing/мед. аудит);
- влияние cancelled/incomplete на итоги визита — записать scope явно;
- N2-3 DoD: atomic claim на call-next, last-completer флипает entry, идемпотентный complete — иначе feature-flag до N2-4;
- tablet: повтор POST тем же nurse = no-op, другим = 409; поведение при деактивации назначения mid-flight (403 или graceful drain).
- Ничего не merge/deploy автоматически.

## Текущее состояние

- 2026-09-18: план создан (срез N2-1), discovery поверхностей зафиксирован выше (Task 3-a, read-only). Ожидает **design-GO владельца**. Runtime-изменений нет.
- 2026-09-19: merge-checklist владельца закрыт в этом PR — коррекции 1–6 применены: нумерация миграций (next available от fresh main, номер не резервируется); service-level execution + ownership-маппинг добавлены (раздел «N2-2 фиксации»); Nurse role enum — re-open retired-значений; статус QD-2/RQ-15 = FROZEN / DONE с 2026-09-18; CLOUD-START.md актуализирован тем же фактом; N2-3 brief владельца перенесён в план. Версия плана 1 → 2. Runtime-изменений по-прежнему нет.
- 2026-09-19: **design-GO владельца на N2-2 (FINAL)** — D1/D2/D3 зафиксированы в разделе «N2-2 design-GO (FINAL)» выше. Preflight выполнен агентом (fresh main `aecf739aa`, single head `0070_lab_results_lineage`, 71 ревизия; production-on-record 0069 → main впереди ровно на 0070; next available revision = 0071; deploy 0070 — отдельное решение владельца, НЕ автоматизируется). Реализация N2-2 (foundation PR): ре-опен роли Nurse (`Roles.NURSE`, вывод 'nurse' из RETIRED_ROLE_SPELLINGS, write-vocabulary user-management, privilege-zero), модель+миграция `nurse_workplace_assignments` (0071: partial UNIQUE active pair, RLS), модель+миграция `service_executions` (0072: UNIQUE(visit_service_id, attempt_no), partial UNIQUE one-active, FK-политики, RLS), admin-контракт назначений (create/read/deactivate, require_roles Admin), зеркала фронтенда (`roles.ts` + сгенерированные контракты), re-scope N-3 retirement-пинов + новые тесты (role contract / service boundary / model / PG migration acceptance). Serving-эндпоинты и tablet НЕ входят (N2-3/N2-5). Владелец: «теперь не нужно снова останавливаться на общей архитектуре после реализации этих моделей. Следующий осмысленный gate — уже конкретный N2-3 API».
- 2026-09-20: **N2-3 runtime GO владельца** («Начинай N2-3 (serving API) отдельным PR», merge #3333 + deploy 0071/0072 подтверждён владельцем). Реализация N2-3 (PR отдельной веткой): assignment-scoped serving API `/api/v1/nurse/serving` (9 операций: workplaces / station board / call-next / start / executions create+complete+incomplete / entry no-show+incomplete), require_active_roles("Nurse") + data-level авторизация ACTIVE-назначением (даже superuser требует строку назначения; Admin сохраняет свои существующие поверхности); переиспользование call-next локинга (canonical order + FOR UPDATE + сериализация claimants на строке DailyQueue); идемпотентность call-next per-Nurse (§6 повтор/reconnect); start = состояние станции (любая назначенная медсестра; visit резолв visit_id-first + station-branch с расширением open|in_progress + линк; open→in_progress через VisitLifecycleService; визит НЕ закрывается); executions по D1 (queue_entry_id обязателен, attempt_no=+1 после incomplete, one-active claim: тот же nurse 200 no-op / другой 409, handover performed_by); **last-completer flip**: guarded UPDATE под локом строки entry — флипает та completion, которая видит ВСЕ station-routed услуги визита терминальными (D3: queue_tag==ресурс+requires_doctor=false; doctor-routed услуги никогда не блокируют); **graceful drain** при деактивации назначения mid-flight (новые операции 403; starter завершает свой in_progress attempt); no-show НЕ трогает sibling-pending услуги (restore-path); entry-incomplete 409 при живых in_progress executions; UserAuditLog actor-attributed на каждую мутацию (словарь online_queue_entries/service_executions, join через get_by_resource). OpenAPI + api.ts регенерированы (хирургический патч по прецеденту #3333 round-2 — pydantic-дельта песочницы не касается новых фрагментов). Тесты: unit 52 + endpoints 8 + openapi-пины 9 операций + §6 PG-concurrency сьют (4 теста, CI-only: две медсестры/один ресурс/два кабинета, одновременный call-next, double-tap идемпотентность, execution race 409, last-completer race ровно один флип) — N2-4 boundary решение: §6 proof включён в N2-3 PR (DoD atomic claim/last-completer/идемпотентный complete без feature-flag). Миграций нет (0071/0072 несут всю схему). Tablet — N2-5.
- 2026-09-21: **N2-5 GO владельца + N2-4 boundary folded into N2-3** («NURSE-V2: следующий срез — N2-5 Tablet UI. Human GO на N2-5 ДАН. N2-4 отдельным PR НЕ делать — обязательный §6 PostgreSQL concurrency acceptance уже включён и доказан внутри N2-3 / PR #3355… В SSOT это уже зафиксировано как: N2-4 boundary folded into N2-3»). Владельцем зафиксирован детальный N2-5 brief (15 разделов): canonical route /nurse, Nurse only (без Nurse→Doctor alias, без Registrar/Admin поверхностей), только N2-3 API-контракт (9 операций), workplace UX (0/1/N), tablet-экран «где работаю / кто сейчас / кто следующий», idempotency/double-tap + 409→refetch, reload-restore только из server state, error UX (401/403/404/409/5xx), polling без нового WS-protocol, PHI-гигиена (никаких ФИО/телефонов/reason в console/analytics), tablet-first 768×1024/1024×768/1366×768, тесты (unit/contract/browser 3 сценария), STOP перед merge, деплой N2-3+N2-5 одним релизом. Единственный допустимый backend blocker среза: graceful-drain reload-recovery discovery, если API недостаточно.
- 2026-09-21: **N2-3 follow-up (drain-recovery discovery) — gap эмпирически доказан и закрыт**. Preflight N2-5 (§8 обязательный edge-case): на fresh main `770cafdaf` (merge #3355 + docs #3357) воспроизведён сценарий деактивации назначения mid-flight: активный execution → assignment деактивирован → reload → GET /workplaces = 0 записей, GET station board = 403, при этом POST complete/incomplete по execution_id = 200 (graceful drain работает). Вывод: после reload НЕТ read-пути восстановления execution_id — drain недостижим из UI без localStorage-workaround (запрещён директивой). По директиве §8 сделан минимальный N2-3 follow-up PR: read-only self-scope `GET /api/v1/nurse/serving/draining-executions` — возвращает in_progress executions, начатые самим вызывающим (started_by_user_id == caller), station chain валидируется (`_execution_station_or_error`, orphaned остаются невидимыми как прежде), исключаются станции с активным назначением (board уже несёт их через in_progress_execution_id); каждый item = execution payload + station (queue_resource_id/code/display_name/historical effective_cabinet) + entry (entry_id/number/patient_name) + service (visit_service_id/code/name/qty). Никаких мутаций/аудита (read-plane как остальные GET), никаких новых authorization-поверхностей. OpenAPI + api.ts — хирургический патч (+1 path, +5 схем NurseServingDraining*; полный локальный экспорт отвергнут из-за pydantic-дельты песочницы — прецедент #3333 round-2). Тесты: unit 4 (discovery после деактивации полный §8-цикл + пуст при активном назначении + чужие невидимы + только последний in_progress attempt) + endpoint 3 (auth-матрица 401/403 + полный router-флоу деактивация→discovery→drain→пусто + пусто для fresh nurse) + openapi-пин 10-й операции. Миграций нет. После этого PR — N2-5 продолжен на его ветке (stacked).
- 2026-09-21: **N2-5 реализован (stacked на follow-up ветке feat/nurse-v2-n2-3-drain-recovery)**. Canonical route /nurse (routeRegistry: id nurse-serving, roles ['Nurse'] — БЕЗ Admin по data-level политике N2-3, homeForRoles nurse ПЕРЕНЕСЁН с clinical-profile, layout hideSidebar — tablet-first frameless, patient-home прецедент); App.tsx lazy NurseTabletPage. Компоненты src/pages/nurse/: NurseTabletPage (workplace UX 0/1/N + board + draining-карточка + notice UX), NurseStationBoard («где работаю/кто сейчас/кто следующий»; кнопки по серверному состоянию: waiting→call-next, called→Начать приём/Не явился/Завершить без выполнения, in_progress→per-service действия), NurseServiceList (pending/completed/incomplete/in_progress + attempt + НЕТ visit-close), NurseIncompleteDialog (reason strip/non-blank/≤200 — зеркало серверного контракта), useNurseServingBoard (state-машина: server-state-only §8, мутации→canonical refetch §7, 409→refetch+notice, 403→workplaces reset, 404→unavailable, 5xx→сохранение rendered state+Retry; polling 30s + focus/visibility 5s throttle §10; localStorage workplace-ключ = UI preference, GET /workplaces = SSOT §4). API-модуль src/api/nurseServing.ts — ТОЛЬКО 10 операций N2-3+follow-up на generated DTO (types/api.ts алиасы, Wave-5: компоненты через boundary-алиасы без *Dto-импортов). i18n: namespace nurse (50 ключей × 5 локалей) + errors.nurse.board_unavailable. PHI-гигиена §11: ноль console.*, ноль client-audit, reason только в clinical endpoint. Тесты: компонентные 17 (workplace 0/1/N, waiting/called/in_progress, double-tap disable, 409/403/network, reason UX blank/trim/overlength, no-visit-close, reload-restore, draining-карточка) + contract 4 (generated-DTO-only, PHI/audit/visit-close/URL-allowlist 10 операций) + i18n-контракт 8 (5 локалей) + routing-пины (routeContract N2-5 describe: /nurse home+roles+frameless; rbacRouteParity: routeToRoles('/nurse')==['Nurse'], nurse отсутствует в SIDEBAR_PRESETS) + e2e business spec 4 (self-contained, моки по authenticatedQa-паттерну: fake JWT + sessionStorage + единый /api/v1/** route-handler). Гейты: tsc 0, vitest 2363/2363 (266 файлов), lint 0 errors, stylelint OK, build ✓, check-theme OK, icon-controls OK. Browser acceptance §13 против disposable backend (uvicorn+sqlite create_all): 15/15 — S1 полный флоу (login→workplace→call-next→RELOAD→restore→start→execution→complete→last-completer флип; визит НЕ закрывается), S2 две медсестры на одном ресурсе → РАЗНЫЕ пациенты, S3 assignment loss mid-flight → reload → draining discovery → graceful drain → карточка исчезает. Responsive §12: 768×1024/1024×768/1366×768 — нет горизонтального скролла, primary actions видимы, touch-targets ≥56px. Миграций нет. N2-3 follow-up PR #3358 — CI 40 чеков 0 red (freshness-фикс openapi байт-точность).
- 2026-09-21: **N2-5 owner review round — backend: server-derived D1 handover predicate**. Вердикт владельца на stacked PR: #3358 (e4a7abd2a) 0/0/0 → MERGED (merge-commit d01ef3096); #3359 (75b202e3d) собственная дельта P1×3+P2×3 → не мержить unchanged; stack разошёлся (#3359 не содержал e4a7abd2a) → rebase на новый main выполнен чисто (5 UI-коммитов, backend/generated дифф #3358 из PR исчез). Fix P1 «handover, разрешённый backend, недоступен через UI»: board GET теперь несёт пер-энтри сервер-производный предикат — `claim_owner_assignment_active` (владелец called_by держит ACTIVE-назначение НА ЭТОЙ станции; для admin-called записи без владельца = false) и `actionable_by_current_user` (свой claim ИЛИ владелец ушёл — ровно тот takeover, который start/terminal эндпоинты санкционируют). Один IN-batch запрос на всю доску (пин константного бюджета обновлён: коллега с активным назначением в _board_world даёт батчу «зубы»); поля только на active-строках (waiting/terminal = None). OpenAPI + api.ts регенерированы (полный локальный экспорт байт-идентичен sand­box-дельта = 0 — прецедент хирургического патча не понадобился). Тесты: unit TestHandoverPredicate 7 (отозванный владелец → actionable; активный владелец → read-only для коллег; свой claim; admin-called без владельца; station-scoped ownership; waiting/terminal без предиката; полный takeover-флоу start→execution→complete→флип) + endpoint 2 (предикат в JSON + read-only кейс). Frontend-часть предиката — следующим коммитом (UI action «Принять пациента / Продолжить обслуживание» + P1×2/P2×3 стейт-машина).
