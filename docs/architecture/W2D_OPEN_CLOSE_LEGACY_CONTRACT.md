# W2D Open / Close Legacy Contract

This document describes the current mounted runtime behavior of the remaining legacy admin endpoints:

- `POST /api/v1/appointments/open-day`
- `POST /api/v1/appointments/close`

Both endpoints belong to the OnlineDay legacy island and sit outside the main `DailyQueue` / `OnlineQueueEntry` allocator track.

## `open_day`

### Mounted path

- `POST /api/v1/appointments/open-day`
- Owner: [appointments.py](C:/final/backend/app/api/v1/endpoints/appointments.py)

### Request shape

Query params:

- `department` (required)
- `date_str` (required, `YYYY-MM-DD`)
- `start_number` (required, integer, `>= 0`)

### Response shape

Returns a plain object:

- `ok`
- `department`
- `date_str`
- `start_number`
- `is_open`
- `last_ticket`
- `waiting`
- `serving`
- `done`

### Mutations performed

`open_day` currently:

1. writes `queue::{dep}::{date}::open = 1` into `Setting(category="queue")`
2. writes `queue::{dep}::{date}::start_number = {start_number}` into `Setting(category="queue")`
3. commits the transaction
4. calls `load_stats(...)`
5. attempts `_broadcast(dep, date_str, stats)`

### State transition performed

Intended meaning in the route docstring: "open the online ticket day / morning intake window".

Actual direct writes:

- legacy queue `Setting(...)` keys are updated
- `OnlineDay.is_open` is **not** explicitly set here
- `OnlineDay.start_number` is **not** explicitly set here

### OnlineDay effect

Indirect only:

- `load_stats(...)` calls `get_or_create_day(...)`
- if the `OnlineDay` row does not exist yet, it may be created with defaults
- if the row already exists, `open_day` does not explicitly reopen it

### Board / stats / counter effect

- yes, it affects board/stat counters through `load_stats(...)`
- yes, it emits legacy `queue.update` websocket side effects through `_broadcast(...)`

## `close_day`

### Mounted path

- `POST /api/v1/appointments/close`
- Owner: [appointments.py](C:/final/backend/app/api/v1/endpoints/appointments.py)

### Request shape

Query params:

- `department` (required)
- `date_str` (required, `YYYY-MM-DD`)

### Response shape

Returns a plain object:

- `ok`
- `department`
- `date_str`
- `is_open`
- `start_number`
- `last_ticket`
- `waiting`
- `serving`
- `done`

### Mutations performed

`close_day` currently:

1. calls `get_or_create_day(..., open_flag=False)`
2. commits the transaction
3. calls `load_stats(...)`
4. returns the loaded stats snapshot

### State transition performed

The route explicitly closes the legacy OnlineDay intake state:

- `OnlineDay.is_open = False`

### OnlineDay effect

Direct:

- the `OnlineDay` row is created if missing
- the row is updated to `is_open=False`

### Board / stats / counter effect

- yes, it affects board/stat views because `load_stats(...)` reads `OnlineDay.is_open`
- unlike `open_day`, the current implementation does **not** call `_broadcast(...)`

## Shared Runtime Notes

- Both routes are admin-only mounted legacy endpoints.
- Both routes still influence the same legacy department/day counter world.
- They are **not** SSOT queue allocation operations.
- They are asymmetric today:
  - `open_day` mutates `Setting(...)` keys and returns a manually constructed "open" response
  - `close_day` mutates `OnlineDay.is_open` directly and returns loaded state
