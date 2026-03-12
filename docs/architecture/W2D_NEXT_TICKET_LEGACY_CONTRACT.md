# W2D next_ticket Legacy Contract

## Endpoint

- Mounted path: `POST /api/v1/queues/next-ticket`
- Current handler: `backend/app/api/v1/endpoints/queues.py::next_ticket()`
- Runtime owner: `backend/app/services/online_queue.py::issue_next_ticket()`

## Request shape

Required query inputs:

- `department: str`
- one of:
  - `d: YYYY-MM-DD`
  - `date: YYYY-MM-DD`

Validation behavior:

- if neither `d` nor `date` is supplied, the route returns `422`
- the route does not currently take a request body

## Response shape

Current response is a small operational payload:

```json
{
  "ticket": 12,
  "stats": {
    "department": "Reg",
    "date_str": "2026-03-10",
    "is_open": true,
    "start_number": 1,
    "last_ticket": 12,
    "waiting": 5,
    "serving": 0,
    "done": 0
  }
}
```

## What it actually does

`next_ticket()` does not call the next waiting patient and does not move a queue entry from `waiting` to `serving`.

Instead it issues the next legacy department/day ticket number inside the OnlineDay counter world:

1. resolves `date_str` from `d` or `date`
2. ensures an `OnlineDay` row exists for `department + date_str`
3. reads legacy `last_ticket` from `Setting(category="queue")`
4. computes `next_ticket = max(last_ticket, start_number - 1) + 1`
5. writes the new `last_ticket`
6. increments legacy `waiting` by `+1`
7. leaves `serving` and `done` unchanged
8. commits the transaction
9. reloads `DayStats`
10. broadcasts a legacy `queue.update` websocket payload

## Data mutation surface

Entities mutated by this flow:

- `OnlineDay`
  - only through `get_or_create_day()`
  - may create the day row if absent
- `Setting(category="queue")`
  - `...::last_ticket`
  - `...::waiting`

Entities not mutated by this flow:

- SSOT `DailyQueue`
- SSOT `OnlineQueueEntry`
- queue-entry status rows
- doctor queue runtime state

## Numbering effect

Yes. This route owns legacy department/day numbering:

- `last_ticket` increments monotonically inside the legacy `department + date_str` namespace
- numbering starts from `start_number - 1`, defaulting effectively to `0` when the day starts at `1`

## Queue-state effect

Yes, but only in legacy counter form:

- `waiting += 1`
- `serving` unchanged
- `done` unchanged

This is counter mutation, not queue-entry lifecycle mutation.

## Board / display effect

Indirectly yes.

The route updates the same legacy stats surface later read by:

- `GET /api/v1/queues/stats`
- `GET /api/v1/board/state`
- legacy queue websocket room payloads via `queue.update`

## Related but not current runtime path

`backend/app/crud/queue.py::next_ticket_and_insert_entry()` exists, but it is not the runtime owner of `POST /api/v1/queues/next-ticket`.

It operates on a different `daily_queues / queue_entries` surface and should be treated as a separate stale helper, not as the current mounted behavior.
