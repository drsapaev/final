# Wave 2C OnlineDay Island Boundary

Date: 2026-03-09
Mode: analysis-first, isolation-first

## Boundary statement

The OnlineDay family is a separate legacy island.

It must not be confused with the SSOT queue domain built around:

- `DailyQueue`
- `OnlineQueueEntry`
- `QueueDomainService.allocate_ticket()`

## What belongs to the OnlineDay island

### Legacy model ownership

- `backend/app/models/online.py` -> `OnlineDay`
- `backend/app/services/online_queue.py` -> department/day counters stored in
  `Setting(category="queue")`

### Live mounted endpoints

- `backend/app/api/v1/endpoints/appointments.py`
  - `open_day()`
  - `stats()`
  - `close_day()`
- `backend/app/api/v1/endpoints/queues.py`
  - `stats()`
  - `next_ticket()`
- `backend/app/api/v1/endpoints/board.py`
  - `board_state()`

### Legacy support / duplicate mirrors

- `backend/app/api/v1/endpoints/online_queue.py` (router disabled)
- `backend/app/services/online_queue_api_service.py`
- `backend/app/services/appointments_api_service.py`
- `backend/app/services/board_api_service.py`
- `backend/app/services/queues_api_service.py`

### Adjacent stale helper, but not the OnlineDay owner

- `backend/app/crud/queue.py`

This file uses a stale counter-style helper model, but it is not the runtime
owner of the mounted OnlineDay surface.

## Legacy-only ownership that remains

OnlineDay still owns its own:

- `last_ticket` numbering
- day-open / day-close state
- waiting / serving / done counters
- board/stats read model
- morning-window logic in the disabled legacy self-join flow

These are legacy-only concepts and are not part of SSOT queue ownership.

## What must never be confused with SSOT queue paths

Do not treat OnlineDay paths as if they were:

- queue-local `DailyQueue` numbering
- canonical duplicate-policy enforcement
- canonical active-entry evaluation
- `queue_time` / `priority` fairness ordering
- `QueueDomainService.allocate_ticket()` callers

## Boundary verdict

The OnlineDay island is still live, but it is outside the main queue allocator
track and should now be handled as:

- legacy compatibility ownership
- later cleanup / retirement planning
- not a migration blocker for the SSOT queue families
