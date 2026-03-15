# Wave 2D OnlineDay Live Surfaces

Date: 2026-03-09
Mode: analysis-first, docs-only

This document isolates the still-live mounted OnlineDay legacy surface that
must be handled before final deprecation of the OnlineDay island.

## Live mounted surfaces

| Surface | Current owner | User-visible purpose | Read / write | Changes queue state? | Replacement complexity |
|---|---|---|---|---:|---|
| `appointments.py::open_day()` | `appointments.py` + local `_upsert_queue_setting()` + `online_queue.load_stats()` + websocket broadcast | Admin opens morning online intake for a department/day and sets `start_number` | Write | Yes | High |
| `appointments.py::stats()` | `appointments.py` + `online_queue.load_stats()` | Admin-compatible day counters for department/day | Read | No | Medium |
| `appointments.py::close_day()` | `appointments.py` + `online_queue.get_or_create_day(open_flag=False)` + `online_queue.load_stats()` | Admin closes morning online intake for a department/day | Write | Yes | High |
| `queues.py::stats()` | `queues.py` + `online_queue.load_stats()` | Legacy queue counters for department/day | Read | No | Medium |
| `queues.py::next_ticket()` | `queues.py` + `online_queue.issue_next_ticket()` | Issues next front-desk ticket in legacy counter flow | Write | Yes | High |
| `board.py::board_state()` | `board.py` + `online_queue.load_stats()` | Board/display read model for counters and open state | Read | No | Medium |
| `online_queue.py` service | `online_queue.py` + `Setting` + `OnlineDay` | Runtime owner for legacy numbering/state/counters | Mixed | Yes | High |
| `online.py::OnlineDay` model | `OnlineDay` + `Setting(category="queue")` ownership | Legacy persistence for day-open/day-close and department/day identity | Mixed | Yes | High |

## Surface notes

### `appointments.open_day()`

- Mounted admin endpoint.
- Owns two different legacy state channels at once:
  - `Setting(category="queue")` keys for `open` and `start_number`
  - `OnlineDay.is_open`-based stats/load path
- Also broadcasts updated state over websocket after mutation.

### `appointments.stats()` and `queues.stats()`

- Both are read-only wrappers over the same legacy `load_stats()` contract.
- They are likely duplicative from a domain perspective, but they should not be
  merged or retired before consumer mapping is explicit.

### `queues.next_ticket()`

- Last live mounted OnlineDay allocator path.
- Still owns legacy `last_ticket` progression and waiting-counter increment.
- Does not belong to the SSOT `DailyQueue` / `OnlineQueueEntry` allocator world.

### `board.state()`

- Read-only surface, but still user-visible if legacy board experience remains
  supported.
- Reads the same counters as legacy stats surfaces and therefore depends on
  consistent counter semantics.

## Complexity interpretation

Safest replacement split:

1. read-only surfaces first:
   - `appointments.stats()`
   - `queues.stats()`
   - `board.state()`
2. write/admin surfaces later:
   - `appointments.open_day()`
   - `appointments.close_day()`
   - `queues.next_ticket()`
3. service/model deprecation last:
   - `online_queue.py`
   - `OnlineDay`
