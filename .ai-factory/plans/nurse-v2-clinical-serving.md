# План трека NURSE-V2: человек-медсестра, не-врачебное клиническое обслуживание

Создан: 2026-09-18. Версия плана: 2 (коррекции merge-checklist владельца 2026-09-18: нумерация миграций, service-level execution, ownership-маппинг, Nurse role enum, статус QD-2/RQ-15).
Статус: **APPROVED — план принят владельцем (merge-checklist 2026-09-18 закрыт в этом PR). N2-2 стартует после merge плана (раздел «После merge — старт N2-2»); runtime-код до design-gate N2-2 не пишется. Ничего не deploy автоматически.**
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
