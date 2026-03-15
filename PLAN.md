# Автономный Post-W2D Plan

## Summary

Продолжать проект в автономном режиме по текущему source of truth из [AI_FACTORY_OPENHANDS_MASTER_PLAN.md](C:/final/docs/status/AI_FACTORY_OPENHANDS_MASTER_PLAN.md): сначала добить review-first bounded cleanup там, где это всё ещё low-risk и доказуемо, затем синхронизировать status/backlog docs, и только после этого переходить к новому strategic audit pass.

Зафиксированные правила для автономного режима:
- приоритет: `cleanup first, docs sync second`
- protected domains (`auth`, `payment`, `queue`, `EMR`) не чистить напрямую; для них разрешён только audit/proof до отдельного plan-gate
- каждый cleanup slice остаётся маленьким, review-first и decision-light

## Execution Changes

### 1. Добить остаток safe/mixed cleanup pool
Выполнять по одному кандидату за раз с жёстким gate:
1. проверить mount owner в `backend/app/api/v1/api.py`
2. проверить published route presence в `backend/openapi.json`
3. проверить отсутствие live imports в `backend/app`, `backend/tests`, `docs`, `frontend`
4. проверить diff с mounted owner на небихевиоральность
5. только после этого удалять duplicate и писать W2D trail

Текущее состояние пула после exploration:
- safe duplicate pool почти исчерпан
- remaining mixed candidates: `clinic_management_api_service.py`, `activation_api_service.py`, `settings_api_service.py`
- remaining protected/mixed-protected candidates: `admin_users`, `admin_providers`, `cashier`, `payment_settings`, `queue_auto_close`, `wait_time_analytics`, `minimal_auth`, `simple_auth`, `password_reset`, `phone_verification`, `two_factor*`, `websocket_auth`, `EMR*`, `section_templates`

Правило выхода:
- если кандидат не проходит любой из 5 gates, не удалять его
- вместо удаления фиксировать его как `blocked / mixed-risk candidate` для later plan-gate
- как только не останется clean survivors вне protected zones, cleanup track считается исчерпанным

### 2. Синхронизировать docs после исчерпания safe cleanup
После того как clean survivors закончатся:
- обновить [OPENHANDS_TASK_BACKLOG.md](C:/final/docs/status/OPENHANDS_TASK_BACKLOG.md) под реальное состояние из master plan
- оставить [AI_FACTORY_OPENHANDS_MASTER_PLAN.md](C:/final/docs/status/AI_FACTORY_OPENHANDS_MASTER_PLAN.md) главным execution source of truth
- перевести backlog из старого `2026-03-06` snapshot в текущую фазу `legacy reduction + deprecation continuation + bounded cleanup`
- явно отметить, что Wave 2C core и Postgres guardrail уже stabilized, а активный track теперь legacy-tail reduction

### 3. Подготовить следующий strategic pass после docs sync
Когда safe cleanup и backlog sync завершены:
- собрать новый residue inventory по remaining mixed/protected candidates
- разделить их на 3 buckets:
  - `mixed-risk but non-protected`
  - `protected audit-only`
  - `not cleanup; real live owner / contract-sensitive`
- для каждого protected bucket сделать отдельный plan-gate, а не silent continuation
- новый автономный execution track открывать только после plan replacement

## Public Interfaces / Contracts

- Для cleanup slices: никаких намеренных runtime API changes; mounted owners и published routes должны оставаться неизменными
- Допустимые interface changes только косвенные:
  - удаление detached duplicate files
  - удаление stale docs references
  - узкий test-boundary adjustment, если тест искусственно требует существование уже удалённого residue
- Для docs sync:
  - [OPENHANDS_TASK_BACKLOG.md](C:/final/docs/status/OPENHANDS_TASK_BACKLOG.md) должен перестать выглядеть как ранний Wave 1/2 backlog
  - master plan остаётся каноническим документом, backlog становится aligned execution index

## Test Plan

После каждого mutating cleanup slice:
- `cd C:\final\backend && pytest tests/test_openapi_contract.py -q`
- `cd C:\final\backend && pytest -q`

Acceptance criteria для каждого slice:
- OpenAPI contract green
- full backend suite green
- mounted route ownership unchanged
- no live import/reference regressions introduced
- если всплывает stale test assumption, фиксить только допущение об обязательном существовании residue, не меняя runtime behavior

Acceptance criteria для docs sync:
- backlog и master plan больше не противоречат друг другу по фазе проекта
- active track, blocked tails и working rules совпадают между документами
- docs не обещают продолжение ранних wave-этапов как текущий execution state

## Assumptions

- пользователь разрешил автономное продолжение без отдельного подтверждения на каждый slice
- по умолчанию продолжается текущий стиль: one-slice-at-a-time, review-first, bounded cleanup
- protected domains остаются за отдельным plan-gate даже в автономном режиме
- если safe cleanup pool фактически исчерпан, следующей работой становится docs/backlog alignment, а не насильственный заход в protected cleanup
