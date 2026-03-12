# W2D appointments.stats legacy contract

## Mounted route

- Path: `GET /api/v1/appointments/stats`
- Owner: [appointments.py](C:/final/backend/app/api/v1/endpoints/appointments.py)
- Mounted name: `stats`
- Auth: requires authenticated user through `get_current_user`

## Request shape

Required query params:

- `department`

Date query aliases:

- `date_str`
- `date`
- `d`

Internally the route normalizes these through `_pick_date(...)`.

## Response shape

The route returns the same legacy `DayStats`-style payload as the other
OnlineDay stats surfaces:

- `department`
- `date_str`
- `is_open`
- `start_number`
- `last_ticket`
- `waiting`
- `serving`
- `done`

## Runtime owner

The endpoint does not compute its own counters.

It delegates directly to:

- `app.services.online_queue.load_stats(...)`

That makes it a duplicate wrapper over the same legacy OnlineDay / `Setting(category="queue")`
counter world already used by:

- `GET /api/v1/queues/stats`
- `GET /api/v1/board/state` (legacy counter side)

## Domain meaning

This route is not an SSOT queue-domain surface.

It is a legacy department/day stats read surface inside the OnlineDay island.
It does not own unique business logic beyond:

- requiring auth
- normalizing date aliases
- echoing the legacy counter snapshot

## Contract observation

From an architectural point of view, `appointments.stats()` currently behaves as
a mounted duplicate read wrapper, not as a unique queue or appointment-domain
contract.
