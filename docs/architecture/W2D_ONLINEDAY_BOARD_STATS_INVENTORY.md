# W2D OnlineDay Board/Stats Inventory

## Scope

This slice covers only the live OnlineDay read surfaces that expose department/day
queue counters or board-facing queue state.

## In-Scope Surfaces

| Surface | Endpoint / Function | Current Legacy Owner | Mounted | Write? | Current Data Source | Duplicate / Overlap | Consumer Visibility |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Board state | `GET /api/v1/board/state` -> `board.py::board_state()` | `app.services.online_queue.load_stats()` | Yes | No | `OnlineDay` + `Setting(category="queue")` counters | Overlaps with `queues.stats()` on counters, but used as board-facing surface | Confirmed frontend consumer: `frontend/src/pages/DisplayBoardUnified.jsx` |
| Queue stats | `GET /api/v1/queues/stats` -> `queues.py::stats()` | `app.services.online_queue.load_stats()` | Yes | No | `OnlineDay` + `Setting(category="queue")` counters | Canonical duplicate of `appointments.stats()`; overlaps with `board_state()` counters | Confirmed frontend consumer: `frontend/src/pages/DisplayBoardUnified.jsx` |
| Appointment stats | `GET /api/v1/appointments/stats` -> `appointments.py::stats()` | `app.services.online_queue.load_stats()` | Yes | No | `OnlineDay` + `Setting(category="queue")` counters | Duplicate wrapper over same `DayStats` payload as `queues.stats()` | No confirmed product consumer in `frontend/src`; only generic API wrapper in `frontend/src/api/services.js` |

## Notes

- All three surfaces currently depend on the same legacy aggregate: `DayStats`
  from `app.services.online_queue`.
- `queues.stats()` is the narrowest live counter surface.
- `board.state()` is user-facing, but its current runtime payload is already
  inconsistent with older board documentation and with parts of the current UI
  expectations.
- `appointments.stats()` should be treated as a duplicate legacy stats wrapper
  until a real product consumer is confirmed.
