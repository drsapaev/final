# План трека NURSE-V2-SS: сменная session/shift capability (design-материалы)

Создан: 2026-10-03. Версия: 2 (приведён к S-FINAL владельца).
Статус: **S-FINAL владельца по S1–S7 ПОЛУЧЕН 2026-10-03 (trace `1a101f752b14d4b9`); документ приведён к вердикту, review findings PR #3569 на `c334725` (P1×1 + P2×3, actionable) закрыты в этой версии. Ожидаются re-review владельца и отдельный merge-GO. Runtime SS-2 НЕ начинается до следующего human GO владельца; deploy запрещён.**
Основание: директива владельца 2026-10-03 «сначала a) + b) design-GO на NURSE-V2» (trace `1a0ff8a2609a1ea1`, выдана после merge #3508; task a) = docs-reconcile #3565, task b) = фланг-контроль main + issue #3564). Трек NURSE-V2 кодово завершён (N2-1…N2-5 слиты, N2-5 = merge `bc335421` 2026-09-24) — единственная названная в треке будущая design-поверхность. Дословные якоря владельца:

> D2 FINAL (2026-09-19): «Ограничение "одна активная очередь на Nurse вообще" НЕ вводится (таблет позже выбирает контекст; **сменная модель — отдельная session/shift capability, не RBAC**).»
> Журнал трека (2026-10-03): «будущие расширения (сменная session/shift модель) — отдельные capabilities по прецеденту D2».

Документ не разрешает runtime сам по себе: решения S1–S7 зафиксированы вердиктом владельца 2026-10-03 (раздел «S-FINAL» ниже), но запуск SS-2 требует отдельного human GO. Наличие плана не разрешает deploy, изменение production-данных или принятие продуктовых решений без владельца.

## Settings

- Testing: yes — контрактные, RBAC/RBAC-смежные негативные (deny-by-default) и обязательные PG-concurrency проверки на срезе (прецедент §6/N2-4-folded).
- Logging: minimal — без ФИО, телефона, диагноза, токенов и полного тела запросов (N2-5 §11 PHI-гигиена переносится как есть).
- Docs: после каждого среза запись в «Текущее состояние» этого файла; родительский журнал — `nurse-v2-clinical-serving.md`.
- Roadmap linkage: дочерняя capability NURSE-V2; registrar-queue-remediation не пересекает.
- Стек: FastAPI / SQLAlchemy / PostgreSQL / Alembic; React 19 / TypeScript / Vite — без новых библиотек.
- **Миграции (дисциплина, исправлена по вердикту владельца 2026-10-03):** fresh origin/main; `alembic heads` — ровно один head; next available revision от fresh main (на 2026-10-03 фактический head main — `0074_join_payload_binding`; в v1 документа ошибочно указывался `0077_daily_queue_policy`, исправлено; номер НЕ резервируется этим документом). Production `alembic_version` (on-record 0069) читается ОТДЕЛЬНО на release preflight — production revision должна лежать на известной ancestor/pending chain; divergence/unknown revision → STOP. **Production lag не блокирует разработку SS-2.** Прежний prerequisite «fresh main == alembic_version production» удалён как неверный development gate.

## Цель и границы

Дать клинике факт дежурства: медсестра открывает смену на станции (QueueResource), работает в ней, завершает; система знает «кто сейчас на дежурстве», атрибутирует операции окном смены и не рвёт начатую работу при закрытии смены. Смена — это ФАКТ работы (кто/где/когда), а не новая роль и не пересмотр RBAC-модели (граница D2 FINAL).

- **В scope:** сущность смены (рабочее имя `nurse_duty_sessions`), жизненный цикл open/switch/close с учётом in-flight работы, server-state восстановление на планшете, координация revocation назначения с активной сменой (обязательная часть SS-2, см. отдельный раздел), PG-concurrency proof.
- **Не в scope (не-цели):** HR/табели/зарплаты; авто-планирование смен из `ScheduleTemplate` (`backend/app/models/schedule.py` — шаблоны приёма врачей для записи, НЕ ростер дежурств; переиспользование запрещено контекстом); публичные графики; новые RBAC-гранты или role enum (D2 FINAL: «не RBAC»); новый WS-протокол (polling-паттерн N2-5 §10); прод-deploy трека (N2-5 brief §15 — отдельное решение владельца, не этот трек); отчёт по сменам (S6 FINAL — отложен в отдельный read-only slice).

## Discovery 2026-10-03 (всё уже существует — не переизобретать)

- **Назначения:** `NurseWorkplaceAssignment` (`backend/app/models/nurse_workplace.py`; миграция 0071: partial UNIQUE active pair, RLS): user_id × queue_resource_id, `cabinet_override` (NULL → `QueueResource.default_cabinet`), `is_active`; inactive = исторические записи (не drift). Сегодня назначение — ВЕЧНОЕ разрешение: активной строки достаточно в любой момент времени; время/факт дежурства нигде не фиксируются.
- **Serving API (N2-3, 10 операций):** `backend/app/services/nurse_serving_api_service.py` + `backend/app/api/v1/endpoints/nurse_serving.py`. Авторизация: `require_active_roles("Nurse")` + data-level ACTIVE-assignment на (caller, queue_resource); даже superuser требует строку назначения на этом плане. Graceful drain: завершение СВОЕГО начатого execution доступно без активного назначения; новые операции — 403. D1 handover predicate: `claim_owner_assignment_active` / `actionable_by_current_user` на каждой active-строке board — takeover called-записи коллегой УЖЕ серверно санкционирован.
- **Executions (D1 FINAL, миграция 0072 + 0073):** attempt-семантика, `started_by`/`performed_by`, one-active partial index — миграция 0072 (`service_executions`); routing snapshot (`queue_resource_id` + `routing_queue_tag_snapshot` + `routing_service_id`, включая guarded backfill и legacy fallback) — отдельная миграция **0073** (`0073_execution_routing_snapshot.py`), иммутабельный исторический факт. Идемпотентность: same state+actor → 200, другой actor → 409.
- **Tablet (N2-5):** `src/pages/nurse/NurseTabletPage` + board/list/dialog, `useNurseServingBoard` (server-state-only restore §8, mutation→canonical refetch §7, 409→refetch, polling 30s/focus 5s §10), `localStorage` только для UI-preference (§4: `GET /workplaces` = SSOT). Workplace UX 0/1/N: текущий выбор станции — клиентское состояние, не факт дежурства.
- **Аудит:** UserAuditLog actor-attributed на каждую мутацию (N2-3) — окно смены может позже агрегироваться БЕЗ новых записей аудита.
- **Пробел, который закрывает capability:** (1) «кто сейчас на дежурстве на станции» — невычислимо (assignments = статические разрешения); (2) смена/уход медсестры не оставляет артефакта — board показывает `current = my_entry ?? первый actionable` без duty-семантики; (3) admin-called записи без владельца-дежурного имеют `claim_owner_assignment_active=false` без контекста «почему» (владелец просто не на смене); (4) нет ответа на вопрос владельца клиники «кто дежурил вчера на процедурной» кроме сырого audit-log.

## Минимальная модель (финализировано S-FINAL владельца 2026-10-03)

`nurse_duty_sessions` (рабочее имя; одна новая таблица, additive-only, 0071/0072/0073 не трогаются):

- `id` PK; `user_id` FK `users.id` (NO ACTION — конвенция 0008/0054: удаление пользователя с живой историей смен запрещено); `queue_resource_id` FK `queue_resources.id` (NO ACTION; QueueResource остаётся справочником без человеческих полей; **QueueResource.id остаётся identity axis** — S7 FINAL).
- `effective_cabinet_snapshot` String(20) nullable — снапшот `assignment.cabinet_override ?? QueueResource.default_cabinet` НА МОМЕНТ открытия смены (прецедент routing-snapshot **0073**; исторический факт не переписывается живыми настройками назначения/справочника — S7 FINAL).
- `started_at` TZ; `close_requested_at` TZ nullable; `ended_at` TZ nullable; `status` CHECK (`active` | `closing` | `closed`) (S3 FINAL). `close_requested_at` разделяет момент ухода («попросили закрыться») от момента фактического завершения drain (`ended_at`) — не смешивать.
- Инвариант по S2 FINAL: **partial UNIQUE на `(user_id)` WHERE `status IN ('active','closing')`** — не более одной незакрытой смены на медсестру вообще. Assignments остаются МНОЖЕСТВЕННЫМИ (одна медсестра может иметь права на procedures + ecg и т.д.) — duty-session отвечает на вопрос «где она фактически работает сейчас». Несколько разных медсестёр могут ОДНОВРЕМЕННО иметь смены на одном QueueResource. PG-only DDL в миграции (прецедент 0065/0071/0072), RLS по образцу 0071/0072.
- Никаких полей в существующих таблицах; никакой связи с `ScheduleTemplate`; роль/гранты не меняются.

## S-FINAL владельца (2026-10-03, trace `1a101f752b14d4b9`) — все семь точек решены

- **S1 FINAL — фазировано, выбран вариант (c).** SS-2/SS-3 v1: duty-session = **operational/accounting fact** (учётный факт). N2-3 serving authorization НЕ ужесточается: ACTIVE `NurseWorkplaceAssignment` остаётся текущим data-level gate. Active duty-session НЕ требуется для call/start/execution/terminal в первой фазе. Будущий переход «assignment + active duty-session» — **отдельный owner GO и отдельный runtime slice после production наблюдения**; скрыто в SS-2/SS-3 не включать. Следствие, зафиксированное владельцем: **v1 session не заявляется security boundary.**
- **S2 FINAL — одна текущая станция на медсестру, вариант (a).** Не более одной session со `status active|closing` на `user_id` вообще (partial UNIQUE выше). Assignments множественные; несколько разных медсестёр могут одновременно иметь смены на одном QueueResource. **Implicit auto-switch НЕ вводится:** переход на другую станцию = close текущей → open новой; если старая session draining/closing — новая пока не открывается.
- **S3 FINAL — drain close.** Поля смены: `started_at`, `close_requested_at` nullable, `ended_at` nullable, `status active|closing|closed`. Close без живой работы: `active → closed`, `close_requested_at = now`, `ended_at = now`. Close с живой работой: `active → closing`, `close_requested_at = now`, `ended_at = NULL`. Когда последний live work разрешён: `closing → closed`, `ended_at = now`. Live work учитывается минимум: active queue entry этой медсестры на этой станции (`called` / `in_progress`); in_progress `ServiceExecution`, начатый этой медсестрой и привязанный к этой station/session window. `close_requested_at` нужен, чтобы не смешивать момент ухода со временем завершения drain. Tablet показывает количество незавершённой работы перед close.
- **S4 FINAL — сохранить существующий cross-Nurse completion.** Рекомендация v1 документа (S4a, starter-bound) **ОТКЛОНЕНА владельцем**. Execution НЕ делается starter-bound; существующий контракт N2-3 сохраняется: `execution.started_by_user_id` = медсестра A; медсестра B с ACTIVE assignment на ту же станцию может complete/incomplete этот in_progress execution; `performed_by_user_id` = фактическая медсестра B; стартер A без active assignment сохраняет bounded graceful-drain своего execution; terminal replay остаётся actor-safe/idempotent. **Новый attempt НЕ создаётся только потому, что исполнитель сменился** — это конфликтует с one-active execution invariant 0072; новый attempt создаётся по существующей семантике после terminal incomplete/cancelled retry, а не handover. Если session A находится `closing` и B завершает её execution — этот completion **участвует в разрешении drain session A**. На сценарий добавить regression pins.
- **S5 FINAL — explicit close only, без cron.** Никакого nightly auto-close. Забытая session: `GET current` восстанавливает её; UI показывает длительность/stale warning; перед новой session пользователь обязан явно закрыть старую. Порог warning — UI/config detail, **не DB invariant**; решение о количестве часов не блокирует SS-2.
- **S6 FINAL — отчёт по сменам отложен.** Отчёт НЕ входит в SS-2/SS-3: сначала накапливаются корректные session facts, позже — отдельный read-only reporting slice. Существующий UserAuditLog не дублируется. При этом open/close/revocation session mutations обязаны иметь обычный actor-attributed audit **в той же транзакции**.
- **S7 FINAL — cabinet snapshot.** `effective_cabinet_snapshot = assignment.cabinet_override ?? QueueResource.default_cabinet` на момент открытия session. Исторический факт не переписывается живыми настройками. QueueResource.id остаётся identity axis.

## Assignment revocation × session lifecycle (обязательная часть SS-2; закрывает Codex P2 #3569)

Вердикт владельца: координация revocation — **не отдельный поздний PR, а integrity contract самой session capability**; входит в срез SS-2.

- Open-session и deactivate-assignment должны **сериализоваться на одной строке `NurseWorkplaceAssignment`**: `SELECT ... FOR UPDATE` строки assignment FIRST.
- **Canonical lock order определяется один раз** и закрепляется PG-тестом (пин порядка блокировок).
- Деактивация assignment выполняется **в той же транзакции**: (1) assignment → inactive; (2) если существует active duty-session этой медсестры: нет live work → session `closed`; есть live work → session `closing` (drain-семантика S3 FINAL).
- **Нельзя оставлять ACTIVE session на уже revoked assignment** — ни в одном interleaving.
- Проверяются **ОБА interleaving**: «open wins first» (open закоммитился первым → деактивация в своей транзакции деактивирует assignment и закрывает/дренит смену) и «deactivate wins first» (деактивация первая → open получает отказ 403, ноль orphan-строк).
- Поверхность деактивации (`NurseWorkplaceApiService.deactivate_assignment`, `backend/app/services/nurse_workplace_api_service.py`) входит в SS-2 test surface; T3 PG-сьюта — канонический пин.

## API-surface sketch (по S-FINAL; все операции assignment-scoped, та же цепочка авторизации N2-3)

- `POST /api/v1/nurse/serving/sessions` — открыть смену на станции активного назначения; double-tap = идемпотентно 200 (та же строка); при уже открытой active-смене на другой станции → 409 (требуется явный close → open; **implicit auto-switch отсутствует** — S2 FINAL); если существующая смена в `closing`/draining — новая пока не открывается (409).
- `GET /api/v1/nurse/serving/sessions/current` — restore-путь планшета (reload = server state SSOT, §4/§8 N2-5); восстанавливает и забытую открытую смену (S5 FINAL).
- `POST /api/v1/nurse/serving/sessions/close` — S3-семантика (200 closed / 202 closing-drain).
- Board payload: + read-only саммари «кто на дежурстве сейчас» (additive поле; PHI-гигиена §11 — только имена пользователей-медсестёр, без контактов); перед close — количество незавершённой работы смены (S3 FINAL).

## Concurrency-proof sketch (§6-стиль; обязательный PG-сьют среза SS-2)

- T1: две медсестры открывают смены на одной станции — обе succeed (S2 FINAL: несколько медсестёр на одном QueueResource допустимо), partial UNIQUE на `user_id` держится.
- T2: double-tap «открыть смену» — идемпотентно, ровно одна строка.
- T3: гонка open × deactivate-assignment — сериализация `SELECT ... FOR UPDATE` строки assignment FIRST (canonical lock order, зафиксированный один раз); **оба interleaving**: open wins first → деактивация в той же транзакции деактивирует assignment и переводит смену в `closed` (нет live work) / `closing` (есть live work); deactivate wins first → open = 403, ноль orphan-строк; в обоих исходах ACTIVE-смена на revoked assignment не остаётся.
- T4: close-drain × параллельное разрешение последнего live work — `closing→closed` ровно один раз, `ended_at` ставит last-resolver.
- T5: cross-Nurse completion в drain: смена A `closing`, медсестра B (ACTIVE assignment на той же станции) завершает execution стартера A — completion участвует в разрешении drain A (S4 FINAL); плюс switch-гонка (close+open на B, пока коллега клеймит на A) — факты станции A стабильны, `FOR UPDATE` по образцу call-next.

## Срезы (PR boundaries; SS-1 gate пройден, SS-2/SS-3 ждут human GO)

| Срез | Содержание | Поверхности | Gate |
|---|---|---|---|
| SS-1 | Этот документ (design-материалы + S-FINAL) | только docs | **S-FINAL владельца по S1–S7 — ПОЛУЧЕНО 2026-10-03**; merge-GO — отдельно |
| SS-2 | Модель + миграция (next available, additive, RLS, partial UNIQUE по S2 FINAL) + session-API (3 операции) + board-поле + **координация revocation (раздел выше)** + registry-обновление + тесты (unit/endpoint/openapi-пины + PG-сьют T1–T5 + lock-order пин по прецеденту N2-4-folded) | `models/nurse_duty_session.py`, **`models/__init__.py` (import в registry)**, `alembic/versions/`, `services/nurse_serving_api_service.py`, `services/nurse_workplace_api_service.py` (deactivate-координация), `endpoints/nurse_serving.py`, `schemas/nurse_serving.py`, openapi/api.ts (хирургический патч по прецеденту #3333 r2) | PR; owner review |
| SS-3 | Tablet UX: «Начать смену»/закрытие/switch/restore по S1–S3/S5 FINAL (счётчик незавершённой работы перед close, stale warning без DB-порога), i18n ×5 локалей, PHI-гигиена §11, компонентные+contract+e2e тесты по паттернам N2-5 | `src/pages/nurse/*`, `useNurseServingBoard`, `api/nurseServing.ts`, `routeRegistry` (роль 'Nurse' — без изменений), i18n-файлы | PR; owner review |

Показ владельцу перед SS-2 (протокол трека, обновлён по вердикту): цель — факт дежурства по S-FINAL; **first-touch файлы — `backend/app/models/nurse_duty_session.py`, `backend/app/models/__init__.py` (+ registry/metadata import validation: модель обязана попасть в зарегистрированный metadata, иначе Alembic autogenerate не увидит drift — Codex P2 #3569)**, новая миграция, `nurse_serving_api_service.py`, `nurse_workplace_api_service.py` (deactivate-координация), `endpoints/nurse_serving.py`, `schemas/nurse_serving.py`; проверки — как в SS-2 выше; **stop conditions — любой конфликт с контрактами 0071/0072/0073** (включая corrective-инварианты 0073, сохраняющие in-flight работу завершаемой после catalog retagging), расхождение с S-FINAL, падение PG-сьюта или lock-order пина, divergence production alembic_version (release preflight).

## Acceptance criteria (по S-FINAL; финальная формулировка за владельцем на SS-2 review)

- Медсестра со своего аккаунта открывает смену ТОЛЬКО на станции активного назначения; повтор = идемпотентно; все операции атрибутируются реальному User.
- Смена v1 НЕ выдаёт НИКАКИХ грантов и НЕ является security boundary (S1 FINAL): denial-матрица N2-3 не меняется вообще (регрессионный пин); active duty-session не требуется для call/start/execution/terminal.
- Вторая смена того же user при active/closing существующей — 409 (partial UNIQUE по S2 FINAL); implicit auto-switch отсутствует; переход = явный close → open; при draining новая смена не открывается.
- Close без живой работы → `closed` немедленно (`close_requested_at = ended_at = now`); с живой работой → `closing`, `ended_at` ставит last-resolver последнего live work; `close_requested_at` ≠ `ended_at` при drain (S3 FINAL); tablet показывает счётчик незавершённой работы перед close.
- Cross-Nurse completion сохранён (S4 FINAL): B с ACTIVE assignment на той же станции complete/incomplete in_progress execution стартера A; `performed_by` = B; новый attempt при handover НЕ создаётся (one-active 0072 не рвётся); terminal replay actor-safe/idempotent; completion B разрешает drain closing-смены A; regression pins на сценарий.
- Revocation-координация: нет ACTIVE-смены на деактивированном assignment; сериализация на строке assignment (`FOR UPDATE` FIRST), canonical lock order закреплён PG-тестом, оба interleaving покрыты.
- Отчёт по сменам в SS-2/SS-3 отсутствует (S6 FINAL); open/close/revocation мутации смены имеют actor-attributed audit в той же транзакции; UserAuditLog не дублируется.
- Reload планшета восстанавливает смену из server state (`GET current`), включая забытую открытую (S5 FINAL); localStorage не несёт состояния смены (§4/§8 прецедент); stale warning — UI/config, без DB-инварианта.
- `effective_cabinet_snapshot` зафиксирован на open по формуле S7 FINAL и не переписывается живыми настройками.
- PG-сьют T1–T5 зелёный на CI; SQLite-пути (create_all conftest) не ломаются (PG-only DDL вне `__table_args__`).

## Не-цели (out of scope)

- RBAC/role enum/public.roles (D2 FINAL); EMR/диагноз/финансы/управление пользователями (§5 NURSE-V2); HR/табели/зарплаты; авто-планирование из ScheduleTemplate; новый WS-протокол; отчёт по сменам (S6 FINAL — отдельный read-only slice позже); nightly auto-close (S5 FINAL); прод-deploy N2-3+N2-5 (§15 brief — отдельная операторская авторизация владельца); изменение истории N-3 и записей N2-2/N2-3/N2-5.

## Разбор review findings PR #3569 (verdict владельца 2026-10-03 на `c334725`; все закрыты в v2)

1. **P1 «Preserve cross-nurse execution completion» (S4)** — закрыто переписыванием S4: рекомендация (a) starter-bound ОТКЛОНЕНА, контракт N2-3 сохранён (см. S4 FINAL; дополнительно: completion преемника участвует в drain closing-смены стартера + regression pins).
2. **P2 «Coordinate assignment revocation with active sessions»** — закрыто новым разделом «Assignment revocation × session lifecycle»: сериализация на строке assignment (`SELECT ... FOR UPDATE` FIRST), canonical lock order + PG-пин, деактивация в той же транзакции закрывает/дренит смену, оба interleaving, поверхность `deactivate_assignment` включена в SS-2. T3 сьюта переформулирован под этот контракт.
3. **P2 «Point routing-snapshot references to migration 0073»** — закрыто: в Discovery и «Минимальной модели» прецедент routing-snapshot указывает на 0073 (`0073_execution_routing_snapshot.py`, включая guarded backfill и legacy fallback); stop conditions SS-2 сохраняют контракты 0071/0072/**0073**.
4. **P2 «Add the model registry to the SS-2 file set»** — закрыто: `backend/app/models/__init__.py` добавлен в first-touch SS-2 вместе с registry/metadata import validation (модель вне registry → Alembic autogenerate не видит drift).

Дополнительно исправлено по вердикту: migration discipline (убран неверный prerequisite «fresh main == alembic_version production»; новая формулировка — см. Settings; production lag не блокирует разработку SS-2) и фактический head миграций main (`0074_join_payload_binding`, в v1 ошибочно `0077_daily_queue_policy`).

## STOP discipline

- S-FINAL по S1–S7 получен — design-gate пройден; **runtime SS-2 НЕ пишется до следующего human GO владельца** (следующий шаг после чистого design PR — SS-2 implementation brief на review).
- Ничего не merge/deploy автоматически; merge этого PR — только по явному merge-GO владельца; номер миграции не резервируется этим документом.
- Старые RQ-срезы не затрагиваются (DEFER-правило E-062 в силе); registrar-queue-remediation не пересекает.

## Текущее состояние

- 2026-10-03: design-GO владельца получен (директива «сначала a) + b) design-GO на NURSE-V2», trace `1a0ff8a2609a1ea1`). Discovery поверхностей выполнен (раздел выше, якоря на fresh main `f1be569`), design-материалы S1–S7 подготовлены. Ожидает S-FINAL владельца. Runtime-изменений нет.
- 2026-10-03: **S-FINAL владельца по S1–S7 получен (trace `1a101f752b14d4b9`), скоуп session/shift capability подтверждён**. Документ приведён к вердикту (v2): S1–S7 зафиксированы FINAL; recommendation S4(a) отклонена — cross-Nurse completion сохранён с drain-участием и regression pins; revocation-координация введена как обязательная часть SS-2 (Codex P2 закрыт); routing-snapshot прецедент исправлен на 0073, stop conditions сохраняют 0071/0072/0073 (Codex P2 закрыт); first-touch SS-2 дополнен `models/__init__.py` + registry/metadata validation (Codex P2 закрыт); migration discipline исправлена (production lag не блокирует разработку; production revision читается на release preflight, divergence → STOP). Fresh-sync PR #3569 выполнен после merge #3565 (`47313821`) — обе append-записи parent plan (`nurse-v2-clinical-serving.md`) сохранены. Находки `c334725` (P1×1 + P2×3) закрыты в этой версии; ожидаются fresh CI, re-review владельца, фиксация exact HEAD; 0 unresolved actionable findings — цель раунда. Runtime SS-2 не начат (ждёт отдельный human GO); deploy запрещён.
