# W2D Open / Close Characterization Inventory

This inventory records the exact runtime owners involved in the current mounted behavior of:

- `POST /api/v1/appointments/open-day`
- `POST /api/v1/appointments/close`

## `open_day`

### Code path

- Route: [appointments.py](C:/final/backend/app/api/v1/endpoints/appointments.py)
- Function: `open_day()`

### State sources touched

- `Setting(category="queue")` via `_upsert_queue_setting(...)`
  - `queue::{dep}::{date}::open`
  - `queue::{dep}::{date}::start_number`
- `OnlineDay` only indirectly through `load_stats(...) -> get_or_create_day(...)`

### Response source

- `start_number` is echoed from request input
- `is_open` is hard-coded to `True`
- `last_ticket`, `waiting`, `serving`, `done` come from `load_stats(...)`

### Broadcast / side-effect path

- calls `_broadcast(department, date_str, stats)` after `load_stats(...)`
- `_broadcast(...)` emits legacy websocket payload `type = "queue.update"`

### Likely drift points

- request `start_number` is not the same thing as `OnlineDay.start_number`
- response `is_open=True` is stronger than the actual state mutation guarantees
- side effects are emitted from stats that come from a different state source than the route’s own `start_number` write

## `close_day`

### Code path

- Route: [appointments.py](C:/final/backend/app/api/v1/endpoints/appointments.py)
- Function: `close_day()`

### State sources touched

- `OnlineDay` through `get_or_create_day(..., open_flag=False)`
- no direct write to `Setting(category="queue")` keys

### Response source

- entire payload is derived from `load_stats(...)`

### Broadcast / side-effect path

- no `_broadcast(...)` call in the current mounted route

### Likely drift points

- mutates a different canonical source than `open_day`
- closes `OnlineDay.is_open`, but does not undo `queue::{dep}::{date}::open`
- lacks matching broadcast behavior

## Shared Runtime Owners

- [online_queue.py](C:/final/backend/app/services/online_queue.py)
  - `get_or_create_day(...)`
  - `load_stats(...)`
  - `_broadcast(...)`
- [online.py](C:/final/backend/app/models/online.py)
  - `OnlineDay`
- `Setting(category="queue")`
  - legacy counter and compatibility state store
