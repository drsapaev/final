# Wave 2D OnlineDay Cleanup Inventory

Date: 2026-03-09
Mode: analysis-first, preparation-first

This inventory reframes the existing OnlineDay isolation evidence into cleanup
planning terms.

| Element | Live / support / dead | Remove now? | Replace first? | Risk level | Dependency notes |
|---|---|---:|---:|---|---|
| `backend/app/api/v1/endpoints/online_queue.py` router | Dead | Yes | No | Low | Router is explicitly disabled in `backend/app/api/v1/api.py`; cleanup should still verify no tests/docs depend on it. |
| `backend/app/api/v1/endpoints/online_queue_legacy.py` | Dead | Yes | No | Low | Unmounted compatibility alias layer; not a runtime OnlineDay owner. |
| `backend/app/crud/queue.py` | Dead | Yes | No | Low | Stale counter helper; no active mounted caller in the legacy island review. |
| `backend/app/services/online_queue_api_service.py` | Support (removed) | Yes | No | Low | Confirmed-unused support mirror; removed in support-cleanup slice after bootstrap/OpenAPI/full-suite validation. |
| `backend/app/services/appointments_api_service.py` | Support (removed) | Yes | No | Low | Runtime-unused mirror; later cleanup updated the service-boundary gate so the stale artifact could be deleted safely. |
| `backend/app/services/board_api_service.py` | Support (removed) | Yes | No | Low | Confirmed-unused support mirror; removed in support-cleanup slice after validation. |
| `backend/app/services/queues_api_service.py` | Support (removed) | Yes | No | Low | Confirmed-unused support mirror; removed in support-cleanup slice after validation. |
| `backend/app/api/v1/endpoints/appointments.py` `qrcode_png()` | Support | No | No | Medium | Mounted compatibility payload, but does not own OnlineDay writes; cleanup depends on confirming frontend/consumer usage. |
| `backend/app/api/v1/endpoints/appointments.py` `open_day()` | Live | No | Yes | High | Live mounted admin path; replacement or explicit retirement decision required before removal. |
| `backend/app/api/v1/endpoints/appointments.py` `stats()` | Live | No | Yes | High | Live mounted stats path over legacy counters; can only be removed after read-model replacement or explicit retirement. |
| `backend/app/api/v1/endpoints/appointments.py` `close_day()` | Live | No | Yes | High | Live mounted admin path; coupled to legacy day-open/day-close state. |
| `backend/app/api/v1/endpoints/queues.py` `stats()` | Live | No | Yes | High | Live mounted legacy stats surface; overlaps with other stats consumers and needs endpoint-level replacement/retirement decision. |
| `backend/app/api/v1/endpoints/queues.py` `next_ticket()` | Live | No | Yes | High | Last live mounted legacy allocator path; cannot be removed before replacement or explicit product retirement. |
| `backend/app/api/v1/endpoints/board.py` `board_state()` | Live | No | Yes | High | Mounted board visibility endpoint over legacy counters; must be replaced if board experience remains supported. |
| `backend/app/services/online_queue.py` service owner | Live | No | Yes | High | Runtime owner behind all live OnlineDay endpoints; deprecation blocked until live mounted surface is retired or replaced. |
| `backend/app/models/online.py` `OnlineDay` model | Live | No | Yes | High | Legacy persistence owner for day-open/day-close state; final removal only after service/endpoints are gone. |

## Inventory verdict

The safest cleanup split is:

1. dead/disabled candidates first
2. support-only mirrors next
3. live mounted surfaces only after replacement or explicit retirement
4. `online_queue.py` and `OnlineDay` model last

That means OnlineDay cleanup should begin with dead/disabled removal, not with
service/model deletion.

## Post-slice update (2026-03-09)

- Removed:
  - `backend/app/api/v1/endpoints/online_queue.py`
  - `backend/app/api/v1/endpoints/online_queue_legacy.py`
- Retained:
  - `backend/app/crud/queue.py`

`backend/app/crud/queue.py` turned out not to be dead for this slice. A focused
bootstrap check exposed a live import from
`backend/app/api/v1/endpoints/mobile_api_extended.py`, so it must stay out of
the OnlineDay dead-surface cleanup path for now.

## Support-cleanup update (2026-03-09)

- Removed:
  - `backend/app/services/online_queue_api_service.py`
  - `backend/app/services/board_api_service.py`
  - `backend/app/services/queues_api_service.py`

## Support-cleanup follow-up (2026-03-11)

- Removed:
  - `backend/app/services/appointments_api_service.py`

The file was later confirmed to be stale support residue rather than a runtime
owner. The only remaining dependency was the service-boundary test artifact,
which was updated to stop expecting a non-runtime appointments service file.
