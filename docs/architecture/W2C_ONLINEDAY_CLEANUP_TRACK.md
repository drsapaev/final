# Wave 2C OnlineDay Cleanup Track

Date: 2026-03-09
Mode: analysis-first, docs-only

## Purpose

This document defines the future cleanup / deprecation track for the OnlineDay
legacy island.

It does not remove runtime code now. It only states what must happen before
cleanup becomes safe.

## Cleanup prerequisites

Before OnlineDay cleanup can begin, the system needs:

1. explicit owner decision for the remaining mounted legacy surface
2. replacement plan for:
   - `appointments.open_day()`
   - `appointments.stats()`
   - `appointments.close_day()`
   - `queues.stats()`
   - `queues.next-ticket()`
   - `board.state()`
3. characterization coverage for the mounted legacy counter behavior
4. migration or retirement decision for board/stats consumers
5. deprecation plan for disabled / duplicate legacy mirrors

## Compatibility risks

### Board and status visibility

`board.state()` and legacy stats endpoints still read OnlineDay counters.
Removing OnlineDay without replacing those reads would break operator-facing
visibility.

### Open / close day state

`appointments.open_day()` and `appointments.close_day()` still own legacy
department/day administration.

### Ticket issuing

`queues.next-ticket()` still issues legacy counter numbers. Cleanup cannot begin
before that path is either retired or explicitly replaced.

## Tests needed before removal

At minimum:

- characterization tests for mounted OnlineDay endpoints
- coverage for legacy `next-ticket` behavior
- board/stats compatibility tests
- deprecation smoke tests proving disabled routers and service mirrors are not
  needed in mounted runtime

## Earlier vs later cleanup candidates

### Earlier candidates

- `backend/app/api/v1/endpoints/online_queue.py` (disabled)
- `backend/app/services/online_queue_api_service.py`
- `backend/app/services/appointments_api_service.py`
- `backend/app/services/board_api_service.py`
- `backend/app/services/queues_api_service.py`
- `backend/app/api/v1/endpoints/online_queue_legacy.py`
- `backend/app/crud/queue.py`

### Later candidates

- `backend/app/services/online_queue.py`
- `backend/app/models/online.py`
- mounted OnlineDay-backed endpoints in:
  - `appointments.py`
  - `queues.py`
  - `board.py`

## Cleanup track verdict

OnlineDay cleanup should happen in its own late legacy track, after:

- mounted legacy endpoints are replaced or retired
- board/stats consumers are migrated
- the last live allocator path `/queues/next-ticket` is resolved
