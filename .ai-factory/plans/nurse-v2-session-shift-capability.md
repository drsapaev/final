# План трека NURSE-V2-SS: сменная session/shift capability (design-материалы)

Создан: 2026-10-03. Версия: 1.
Статус: **PROPOSED — design-материалы подготовлены агентом по design-GO владельца 2026-10-03; ожидает S-решений владельца (design-gate). Runtime-работа не начата, миграций нет, deploy не разрешён.**
Основание: директива владельца 2026-10-03 «сначала a) + b) design-GO на NURSE-V2» (trace `1a0ff8a2609a1ea1`, выдана после merge #3508; task a) = docs-reconcile #3565, task b) = фланг-контроль main + issue #3564). Трек NURSE-V2 кодово завершён (N2-1…N2-5 слиты, N2-5 = merge `bc335421` 2026-09-24) — единственная названная в треке будущая design-поверхность. Дословные якоря владельца:

> D2 FINAL (2026-09-19): «Ограничение "одна активная очередь на Nurse вообще" НЕ вводится (таблет позже выбирает контекст; **сменная модель — отдельная session/shift capability, не RBAC**).»
> Журнал трека (2026-10-03): «будущие расширения (сменная session/shift модель) — отдельные capabilities по прецеденту D2».

**Интерпретация скоупа (проверяется на design-review):** «design-фаза NURSE-V2» = подготовка design-материалов следующей capability трека — сменной session/shift модели. Если владелец имел в виду иной скоуп — документ правится до S-FINAL без потерь (docs-only, runtime не начинался).

Документ не разрешает runtime: решения S1–S7 ниже фиксируются ТОЛЬКО владельцем (прецедент design-gate N2-2: D1/D2/D3 FINAL). Наличие плана не разрешает deploy, изменение production-данных или принятие продуктовых решений без владельца.

## Settings

- Testing: yes — контрактные, RBAC/RBAC-смежные негативные (deny-by-default) и обязательные PG-concurrency проверки на срезе (прецедент §6/N2-4-folded).
- Logging: minimal — без ФИО, телефона, диагноза, токенов и полного тела запросов (N2-5 §11 PHI-гигиена переносится как есть).
- Docs: после каждого среза запись в «Текущее состояние» этого файла; родительский журнал — `nurse-v2-clinical-serving.md`.
- Roadmap linkage: дочерняя capability NURSE-V2; registrar-queue-remediation не пересекает.
- Стек: FastAPI / SQLAlchemy / PostgreSQL / Alembic; React 19 / TypeScript / Vite — без новых библиотек.
- Миграции: next available Alembic revision от fresh origin/main на момент PR (на 2026-10-03 head `0077_daily_queue_policy`; номер НЕ резервируется этим документом). Перед migration PR: fetch + rebase, `alembic heads` — ровно один head, fresh main == alembic_version production (on-record 0069).

## Цель и границы

Дать клинике факт дежурства: медсестра открывает смену на станции (QueueResource), работает в ней, завершает; система знает «кто сейчас на дежурстве», атрибутирует операции окном смены и не рвёт начатую работу при закрытии смены. Смена — это ФАКТ работы (кто/где/когда), а не новая роль и не пересмотр RBAC-модели (граница D2 FINAL).

- **В scope:** сущность смены (рабочее имя `nurse_duty_sessions`), жизненный цикл open/switch/close с учётом in-flight работы, server-state восстановление на планшете, опциональное (решение S1) подключение смены к data-level авторизации serving-операций, PG-concurrency proof.
- **Не в scope (не-цели):** HR/табели/зарплаты; авто-планирование смен из `ScheduleTemplate` (`backend/app/models/schedule.py` — шаблоны приёма врачей для записи, НЕ ростер дежурств; переиспользование запрещено контекстом); публичные графики; новые RBAC-гранты или role enum (D2 FINAL: «не RBAC»); новый WS-протокол (polling-паттерн N2-5 §10); прод-deploy трека (N2-5 brief §15 — отдельное решение владельца, не этот трек).

## Discovery 2026-10-03 (всё уже существует — не переизобретать)

- **Назначения:** `NurseWorkplaceAssignment` (`backend/app/models/nurse_workplace.py`; миграция 0071: partial UNIQUE active pair, RLS): user_id × queue_resource_id, `cabinet_override` (NULL → `QueueResource.default_cabinet`), `is_active`; inactive = исторические записи (не drift). Сегодня назначение — ВЕЧНОЕ разрешение: активной строки достаточно в любой момент времени; время/факт дежурства нигде не фиксируются.
- **Serving API (N2-3, 10 операций):** `backend/app/services/nurse_serving_api_service.py` + `backend/app/api/v1/endpoints/nurse_serving.py`. Авторизация: `require_active_roles("Nurse")` + data-level ACTIVE-assignment на (caller, queue_resource); даже superuser требует строку назначения на этом плане. Graceful drain: завершение СВОЕГО начатого execution доступно без активного назначения; новые операции — 403. D1 handover predicate: `claim_owner_assignment_active` / `actionable_by_current_user` на каждой active-строке board — takeover called-записи коллегой УЖЕ серверно санкционирован.
- **Executions (D1 FINAL, миграция 0072):** attempt-семантика, `started_by`/`performed_by`, one-active partial index, routing snapshot (`queue_resource_id` + `routing_queue_tag_snapshot` — иммутабельный исторический факт, прецедент снапшота). Идемпотентность: same state+actor → 200, другой actor → 409.
- **Tablet (N2-5):** `src/pages/nurse/NurseTabletPage` + board/list/dialog, `useNurseServingBoard` (server-state-only restore §8, mutation→canonical refetch §7, 409→refetch, polling 30s/focus 5s §10), `localStorage` только для UI-preference (§4: `GET /workplaces` = SSOT). Workplace UX 0/1/N: текущий выбор станции — клиентское состояние, не факт дежурства.
- **Аудит:** UserAuditLog actor-attributed на каждую мутацию (N2-3) — окно смены может позже агрегироваться БЕЗ новых записей аудита.
- **Пробел, который закрывает capability:** (1) «кто сейчас на дежурстве на станции» — невычислимо (assignments = статические разрешения); (2) смена/уход медсестры не оставляет артефакта — board показывает `current = my_entry ?? первый actionable` без duty-семантики; (3) admin-called записи без владельца-дежурного имеют `claim_owner_assignment_active=false` без контекста «почему» (владелец просто не на смене); (4) нет ответа на вопрос владельца клиники «кто дежурил вчера на процедурной» кроме сырого audit-log.

## Минимальная модель (предложение агента; финализируется S-решениями)

`nurse_duty_sessions` (рабочее имя; одна новая таблица, additive-only, 0071/0072 не трогаются):

- `id` PK; `user_id` FK `users.id` (NO ACTION — конвенция 0008/0054: удаление пользователя с живой историей смен запрещено); `queue_resource_id` FK `queue_resources.id` (NO ACTION; QueueResource остаётся справочником без человеческих полей).
- `effective_cabinet_snapshot` String(20) nullable — снапшот `cabinet_override ?? default_cabinet` НА МОМЕНТ открытия (прецедент routing-snapshot 0072: факт старта не переписывается живыми изменениями назначения).
- `started_at` TZ; `ended_at` TZ nullable; `status` CHECK (`active` | `closing` | `closed`) — `closing` = запрос закрытия при живой in-flight работе (S3, drain-семантика).
- Инвариант(ы) по S2: partial UNIQUE ровно одной незакрытой смены — `WHERE status IN ('active','closing')`; варианты: на `(user_id)` (одна смена на медсестру вообще) или `(user_id, queue_resource_id)` (параллельный дежурный пост допустим). PG-only DDL в миграции (прецедент 0065/0071/0072), RLS по образцу 0071/0072.
- Никаких полей в существующих таблицах; никакой связи с `ScheduleTemplate`; роль/гранты не меняются.

## Решения владельца (S-точки; каждая — options + рекомендация агента)

- **S1 — Позиционирование смены (главная точка).** (a) Авторизационная: новые serving-операции требуют assignment + ACTIVE session (ужесточает data-level чек N2-3; чужая смена → 403 «не на смене»; нужен graceful-path для closing); (b) Учётная: смена = факт/атрибуция/отчётность, авторизация остаётся assignment-only (ноль изменений в доказанном N2-3 плане); (c) Фазировано: v1 = (b), флип на (a) отдельной директивой владельца после прод-валидации смен. Рекомендация: (c) — риск для работающего serving-плана нулевой, факты накапливаются с первого дня, флип аддитивен. Обе (a)/(b) совместимы с D2 FINAL «не RBAC» (data-level, роли не трогаются).
- **S2 — Гранулярность активной смены.** (a) Одна незакрытая смена на медсестру вообще (переключение станции = close+open одной операцией, tablet «где я сейчас» тривиален, handover-история линейна); (b) Разрешить параллельные посты `(user_id, queue_resource_id)` (симметрично D2 multi-assignment, но усложняет UX/инварианты). Рекомендация: (a).
- **S3 — Закрытие смены при живой работе.** (a) Запретить close пока есть мои in-flight (нужно разрулить вручную); (b) Drain-close: close переводит смену в `closing`, `ended_at` ставится фактом последнего разрешения собственного in-flight (прямо переиспользует решение N2-3 о graceful drain и one-active invariant 0072); (c) Hard close с принудительным orphan-разбором — против течения существующих инвариантов. Рекомендация: (b) + tablet-гвард «на смене N незавершённых» перед close.
- **S4 — Handover преемником.** Called-записи: takeover УЖЕ работает через `actionable_by_current_user` (номер не нужен — ничего не делаем). Executions: сейчас starter-bound (чужой → 409 by design). (a) Оставить starter-bound в v1 (закрытие смены по S3 drain вынуждает стартера дожать/пометить incomplete; преемник начинает НОВЫЙ attempt — история честная); (b) Разрешить станционный takeover in_progress attempts при пересекающихся сменах (меняет семантику one-active claim 0072 — отдельный design-риск). Рекомендация: (a), пересмотр по данным живой клиники.
- **S5 — Авто-закрытие забытых смен.** (a) Нет авто-закрытия вовсе (только explicit close) + notice на board «смена открыта Nч» (N фиксирует владелец); (b) Ночной cron-закрытие — новый плановый механизм, против STOP-дисциплины трека. Рекомендация: (a).
- **S6 — Отчёт по смене (summary за окно).** (a) В v1 (агрегат calls/serves/no-shows/incompletes на close); (b) Отложить (UserAuditLog + timestamps уже атрибутируют; отчёт — отдельный read-срез без блокировки capability). Рекомендация: (b).
- **S7 — Кабинет в смене.** Снапшот при открытии (рекомендация, прецедент 0072) vs живой джойн к assignment (переписывает факт задним числом). Рекомендация: снапшот.

## API-surface sketch (уточняется после S-FINAL; все операции assignment-scoped, та же цепочка авторизации N2-3)

- `POST /api/v1/nurse/serving/sessions` — открыть смену на станции активного назначения; double-tap = идемпотентно 200 (та же строка); при S2a открытая смена на другой станции → 409 с телом «switch-семантика».
- `GET /api/v1/nurse/serving/sessions/current` — restore-путь планшета (reload = server state SSOT, §4/§8 N2-5).
- `POST /api/v1/nurse/serving/sessions/close` — S3-семантика (200 closed / 202 closing-drain).
- Board payload: + read-only саммари «кто на дежурстве сейчас» (additive поле; PHI-гигиена §11 — только имена пользователей-медсестёр, без контактов).

## Concurrency-proof sketch (§6-стиль; обязательный PG-сьют среза SS-2)

T1: две медсестры открывают смены на одной станции — обе succeed при S2a, pair-инвариант держится (если S2b — ожидание по решению). T2: double-tap «открыть смену» — идемпотентно, ровно одна строка. T3: гонка open × деактивация назначения mid-request — 403 и ноль orphan-строк. T4: close-drain × параллельное завершение последнего собственного attempt — `closing→closed` ровно один раз, `ended_at` ставит last-resolver. T5: switch-гонка (close+open на B, пока коллега клеймит на A) — факты станции A стабильны, `FOR UPDATE` по образцу call-next.

## Срезы (предполагаемые PR boundaries; фиксируются на S-FINAL)

| Срез | Содержание | Поверхности | Gate |
|---|---|---|---|
| SS-1 | Этот документ (design-материалы) | только docs | **S-FINAL владельца по S1–S7** |
| SS-2 | Модель + миграция (next available, additive, RLS) + session-API (3 операции) + board-поле + тесты (unit/endpoint/openapi-пины + PG-сьют T1–T5 по прецеденту N2-4-folded) | `models/`, `alembic/versions/`, `services/nurse_serving_api_service.py`, `endpoints/nurse_serving.py`, `schemas/nurse_serving.py`, openapi/api.ts (хирургический патч по прецеденту #3333 r2) | PR; owner review |
| SS-3 | Tablet UX: «Начать смену»/закрытие/switch/restore по S1-решению, i18n ×5 локалей, PHI-гигиена §11, компонентные+contract+e2e тесты по паттернам N2-5 | `src/pages/nurse/*`, `useNurseServingBoard`, `api/nurseServing.ts`, `routeRegistry` (роль 'Nurse' — без изменений), i18n-файлы | PR; owner review |

Показ владельцу перед SS-2 (протокол трека): цель — факт дежурства по S-FINAL; first-touch файлы — `backend/app/models/nurse_duty_session.py`, новая миграция, `nurse_serving_api_service.py`, `endpoints/nurse_serving.py`, `schemas/nurse_serving.py`; проверки — как в SS-2 выше; stop conditions — любой конфликт с инвариантами 0071/0072, расхождение с S-FINAL, падение PG-сьюта.

## Acceptance criteria (draft — финальная формулировка за владельцем после S-FINAL)

- Медсестра со своего аккаунта открывает смену ТОЛЬКО на станции активного назначения; повтор = идемпотентно; все операции атрибутируются реальному User (`started_by`-аналог в сессии + существующие атрибуции N2-3 не дублируются).
- Смена не выдаёт НИКАКИХ грантов сверх S1-решения; при S1=(b) denial-матрица N2-3 не меняется вообще (регрессионный пин).
- Закрытие смены не рвёт in-flight работу (S3); преемник начинает новый attempt, а не дописывает чужой (S4a) — или takeover-семантика по S4b.
- Reload планшета восстанавливает смену из server state; localStorage не несёт состояния смены (§4/§8 прецедент).
- Deny: чужая станция без активного назначения — 403; вторая параллельная смена — по S2; операции вне смены — по S1.
- PG-сьют T1–T5 зелёный на CI; SQLite-пути (create_all conftest) не ломаются (PG-only DDL вне `__table_args__`).

## Не-цели (out of scope)

- RBAC/role enum/public.roles (D2 FINAL); EMR/диагноз/финансы/управление пользователями (§5 NURSE-V2); HR/табели/зарплаты; авто-планирование из ScheduleTemplate; новый WS-протокол; прод-deploy N2-3+N2-5 (§15 brief — отдельная операторская авторизация владельца); изменение истории N-3 и записей N2-2/N2-3/N2-5.

## STOP discipline

- До S-FINAL владельца по S1–S7 — никакой runtime-работы по capability (прецедент: «runtime-код до design-gate не пишется»).
- Ничего не merge/deploy автоматически; номер миграции не резервируется этим документом.
- Старые RQ-срезы не затрагиваются (DEFER-правило E-062 в силе); registrar-queue-remediation не пересекает.

## Текущее состояние

- 2026-10-03: design-GO владельца получен (директива «сначала a) + b) design-GO на NURSE-V2», trace `1a0ff8a2609a1ea1`). Discovery поверхностей выполнен (раздел выше, якоря на fresh main `f1be569`), design-материалы S1–S7 подготовлены. Ожидает S-FINAL владельца. Runtime-изменений нет.
