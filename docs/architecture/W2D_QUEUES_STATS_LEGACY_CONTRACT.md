# W2D Queues Stats Legacy Contract

## Endpoint

- Path: `GET /api/v1/queues/stats`
- Current owner: `app.api.v1.endpoints.queues.stats()`
- Legacy aggregate source: `app.services.online_queue.load_stats()`
- Legacy data model:
  - `OnlineDay`
  - `Setting(category="queue")` counters

## Request Contract

Required query params:

- `department`
- one of:
  - `d`
  - `date`

If both `d` and `date` are missing, the endpoint returns `422` with:

- `Query param 'd' or 'date' is required`

## Current Response Shape

The endpoint returns `asdict(DayStats)` from `app.services.online_queue`:

| Field | Type | Current semantic meaning | Current source | UI relevance |
| --- | --- | --- | --- | --- |
| `department` | `string` | Legacy department namespace for the day | `OnlineDay.department` | Low for confirmed consumer |
| `date_str` | `string` | Legacy day key (`YYYY-MM-DD`) | request-normalized `date_str` / `OnlineDay.date_str` | Low for confirmed consumer |
| `is_open` | `boolean` | Whether the legacy department-day is open | `OnlineDay.is_open` | Not used by confirmed `queues.stats` consumer |
| `start_number` | `integer \| null` | Legacy ticket start for the department-day | `OnlineDay.start_number` | Not used by confirmed `queues.stats` consumer |
| `last_ticket` | `integer` | Last issued legacy ticket number | `Setting(category=\"queue\", key=\"<dep>::<date>::last_ticket\")` | Yes |
| `waiting` | `integer` | Legacy waiting counter | `Setting(...\"waiting\")` | Yes |
| `serving` | `integer` | Legacy serving counter | `Setting(...\"serving\")` | Yes |
| `done` | `integer` | Legacy completed counter | `Setting(...\"done\")` | Yes |

## Legacy Contract Notes

- This is a pure OnlineDay-island response. It does not read from `DailyQueue` or
  `OnlineQueueEntry`.
- `last_ticket`, `waiting`, `serving`, and `done` are not derived from queue-row
  state. They are standalone counters stored in `Setting(category="queue")`.
- `is_open` and `start_number` come from `OnlineDay` and therefore carry legacy
  department/day semantics, not SSOT queue semantics.

## Duplicate / Overlap Surface

The same legacy `DayStats` shape is currently exposed through:

- `GET /api/v1/queues/stats`
- `GET /api/v1/appointments/stats`
- `GET /api/v1/board/state`

`queues.stats()` is the narrowest confirmed live counter surface and therefore the
best first replacement candidate.

## Current Consumer-Relevant Contract

For the confirmed live board consumer, the practical contract is smaller than the
 raw response:

- required in practice:
  - `last_ticket`
  - `waiting`
  - `serving`
  - `done`
- present for legacy compatibility but not confirmed as required by the current UI:
  - `department`
  - `date_str`
  - `is_open`
  - `start_number`
