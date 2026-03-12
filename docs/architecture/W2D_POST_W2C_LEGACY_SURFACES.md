# W2D Post-W2C Legacy Surfaces

Wave 2C closed the main production queue allocator track, but a narrow set of legacy surfaces still remains around the OnlineDay island and board compatibility. This document lists those surfaces in a cleanup/reduction-oriented way.

## Remaining Surfaces

| Surface | Endpoint / Owner | Current owner | Domain meaning | Confirmed consumer | External usage risk | Architectural impact |
| --- | --- | --- | --- | --- | --- | --- |
| Legacy board route | `GET /api/v1/board/state` in `backend/app/api/v1/endpoints/board.py` | `backend/app/services/online_queue.py::load_stats()` | Legacy board/read payload for department/day counters | Yes: `frontend/src/pages/DisplayBoardUnified.jsx` still uses it as compatibility fallback | Yes | Medium: route is still mounted, but most board metadata already moved to the additive board-display endpoint |
| Board compatibility flags | `is_paused`, `is_closed` consumed in `frontend/src/pages/DisplayBoardUnified.jsx` | No confirmed backend owner; currently compatibility/default path | Display-only operational flags shown on the board page | Yes | Yes | Medium: legacy route reduction is blocked until these fields get explicit semantics and ownership |
| Legacy queue stats compatibility fields | `is_open`, `start_number` returned from `GET /api/v1/queues/stats` | `backend/app/services/online_queue.py::load_stats()` and `OnlineDay`/`Setting(category="queue")` state | Compatibility-only fields in partially migrated queue stats | No confirmed live consumer for these exact fields | Yes | Low to medium: strict counters already moved, but these fields keep a thin OnlineDay dependency alive |
| Legacy ticket issuance route | `POST /api/v1/queues/next-ticket` in `backend/app/api/v1/endpoints/queues.py` | `backend/app/services/online_queue.py::issue_next_ticket()` | Issues the next department/day legacy ticket and increments legacy waiting counter | No confirmed in-repo consumer | Yes | High: still a live mutating route inside the OnlineDay island |
| Legacy open-day route | `POST /api/v1/appointments/open-day` in `backend/app/api/v1/endpoints/appointments.py` | `OnlineDay` plus queue `Setting(...)` keys | Opens a department/day legacy ticket window and seeds `start_number`/open flag | No confirmed in-repo consumer | Yes | High: still a live mutating admin surface |
| Legacy close-day route | `POST /api/v1/appointments/close` in `backend/app/api/v1/endpoints/appointments.py` | `OnlineDay` via `get_or_create_day(..., open_flag=False)` | Closes a department/day legacy ticket window | No confirmed in-repo consumer | Yes | High: still a live mutating admin surface |
| OnlineDay runtime owner | `backend/app/services/online_queue.py` | Legacy OnlineDay island | Owns legacy stats loading, ticket issuance, and board/websocket-facing counter behavior | Yes, through mounted legacy routes | No | High: this is the main live runtime owner for the remaining OnlineDay behavior |
| OnlineDay model | `backend/app/models/online.py::OnlineDay` | Legacy model | Stores department/day open-state and start-number semantics | Yes, through legacy services/endpoints | No | High: model still anchors open/close and legacy counter defaults |
| Legacy counter sidecar | `Setting(category="queue")` keys, owned from `backend/app/services/online_queue.py` | Legacy counter storage | Persists `open`, `start_number`, `last_ticket`, `waiting`, `serving`, `done` | Yes, through legacy routes | No | High: core mutable data for the remaining OnlineDay island |
| Legacy queue websocket fragment | `backend/app/services/online_queue.py::_broadcast()` emitting `type = "queue.update"` | Legacy queue broadcast path | Broadcasts legacy department/day counter snapshots after open-day / next-ticket changes | No confirmed in-repo direct consumer for the dotted event name | Yes | Medium: likely external/manual or backward-compat traffic, but no longer part of the main allocator architecture |
| Retained support-only artifact | `backend/app/services/appointments_api_service.py` | Support/test architecture surface | Service mirror for legacy appointments endpoints retained after support cleanup | Yes, but only as architecture/test artifact | No | Low: not a runtime owner, but still blocks full support-surface cleanup |

## Notes

- The main queue allocator architecture built around `DailyQueue` and `OnlineQueueEntry` is already complete. The surfaces above remain because they either:
  - still represent live legacy admin/runtime behavior, or
  - are blocked by unresolved product/contract semantics.
- `DisplayBoardUnified.jsx` is already mostly off the legacy board route. The remaining dependency is narrow and centered on `is_paused` / `is_closed`.
- `POST /api/v1/queues/next-ticket` remains mounted even though no in-repo direct caller was confirmed; external/manual usage cannot be ruled out.
