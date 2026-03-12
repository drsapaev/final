# Wave 2C OnlineDay Legacy Inventory

Date: 2026-03-09
Mode: analysis-first, docs-only

## Summary

`OnlineDay` remains in the repository as a legacy department/day counter world.
It is no longer part of the main `DailyQueue` / `OnlineQueueEntry` SSOT flows,
but it still has a small mounted runtime surface.

The live legacy surface is concentrated around:

- `appointments` admin/status endpoints
- `queues` stats and next-ticket endpoints
- `board` read model
- `services/online_queue.py` as the shared legacy runtime owner

There is no runtime bridge that converts `OnlineDay` state into SSOT
`DailyQueue` / `OnlineQueueEntry` state. Coexistence is side-by-side.

## Inventory

| File | Function / surface | Mounted | Production relevant | Legacy numbering | Legacy queue semantics | Bridge to new queue system | Current risk level | Recommended disposition |
|---|---|---:|---:|---:|---:|---:|---|---|
| `backend/app/models/online.py` | `OnlineDay` model | No | Yes, indirect | No | Yes | No | High | Keep isolated as legacy model |
| `backend/app/services/online_queue.py` | `get_or_create_day()` | No | Yes, indirect | No | Yes | No | High | Runtime owner for legacy day-open state |
| `backend/app/services/online_queue.py` | `load_stats()` | No | Yes, indirect | Reads `last_ticket` | Yes | No | High | Runtime owner for legacy stats |
| `backend/app/services/online_queue.py` | `issue_next_ticket()` | No | Yes, indirect | Yes | Yes | No | Very High | Only live legacy allocator path |
| `backend/app/services/online_queue.py` | `is_within_morning_window()` / `can_issue_more_today()` | No | No for current mounted runtime | Yes, indirectly | Yes | No | Medium | Legacy join-only support; not part of current mounted production flow |
| `backend/app/services/online_queue.py` | `get_existing_ticket_for_identity()` / `remember_identity_ticket()` | No | No for current mounted runtime | Yes, indirectly | Yes | No | Medium | Disabled-router duplicate memory only |
| `backend/app/api/v1/endpoints/appointments.py` | `open_day()` | Yes | Yes | Sets start-number baseline only | Yes | No | Medium | Live legacy admin path |
| `backend/app/api/v1/endpoints/appointments.py` | `stats()` | Yes | Yes | Reads `last_ticket` | Yes | No | Medium | Live legacy read path |
| `backend/app/api/v1/endpoints/appointments.py` | `close_day()` | Yes | Yes | No | Yes | No | Medium | Live legacy admin path |
| `backend/app/api/v1/endpoints/appointments.py` | `qrcode_png()` | Yes | Yes | No | No | No | Low | Compatibility-only text payload |
| `backend/app/api/v1/endpoints/queues.py` | `stats()` | Yes | Yes | Reads `last_ticket` | Yes | No | Medium | Live legacy read path |
| `backend/app/api/v1/endpoints/queues.py` | `next_ticket()` | Yes | Yes | Yes | Yes | No | Very High | Live legacy allocator path |
| `backend/app/api/v1/endpoints/board.py` | `board_state()` | Yes | Yes | Reads `last_ticket` | Yes | No | Medium | Live legacy board read model |
| `backend/app/api/v1/endpoints/online_queue.py` | `/online-queue/*` aliases and `join_online_queue()` | No (router disabled in `api.py`) | No | Yes | Yes | No | Medium | Disabled compatibility router |
| `backend/app/services/online_queue_api_service.py` | Legacy online queue service mirror | No | No | Yes | Yes | No | Low | Duplicate/unmounted service mirror |
| `backend/app/services/appointments_api_service.py` | Legacy appointments queue mirror | No direct mount | No clear runtime ownership | Reads `last_ticket` | Yes | No | Low | Duplicate service mirror |
| `backend/app/services/board_api_service.py` | Legacy board queue mirror | No direct mount | No clear runtime ownership | Reads `last_ticket` | Yes | No | Low | Duplicate service mirror |
| `backend/app/services/queues_api_service.py` | Legacy queues mirror | No direct mount | No clear runtime ownership | Yes | Yes | No | Low | Duplicate service mirror |
| `backend/app/crud/queue.py` | `ensure_daily_queue()`, `next_ticket_and_insert_entry()`, `stats_for_daily()` | No | No clear runtime caller | Yes | Yes | No | Medium | Stale adjacent legacy helper; cleanup candidate, not `OnlineDay` owner |

## Mounted status notes

- `backend/app/api/v1/api.py` still mounts:
  - `appointments.router`
  - `queues.router`
  - `board.router`
  - `queue_router` under `/queue/legacy`
- `backend/app/api/v1/endpoints/online_queue.py` is explicitly disabled in
  `api.py`, so its self-join path is not part of the mounted runtime.
- `backend/app/api/v1/endpoints/online_queue_legacy.py` was inspected as well:
  it is unmounted and delegates to QR flows, not to `OnlineDay`.

## Inventory verdict

`OnlineDay` is not dead code, but its live production surface is small and
highly localized. The main live allocator remains `POST /queues/next-ticket`,
while the rest of the mounted OnlineDay family is mostly admin/read behavior.
