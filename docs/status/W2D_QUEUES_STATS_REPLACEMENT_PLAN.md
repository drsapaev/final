# W2D queues.stats replacement plan

## Old legacy path
- [queues.py](C:/final/backend/app/api/v1/endpoints/queues.py) `stats()`
- strict counters and compatibility fields all came from `load_stats(...)`

## New strict SSOT-backed fields
- `last_ticket`
- `waiting`
- `serving`
- `done`

These fields will come from the SSOT candidate read-model in
[queue_stats_parity_harness.py](C:/final/backend/app/services/queue_stats_parity_harness.py).

## Compatibility fallback fields
- `is_open`
- `start_number`

These stay legacy-backed for now because they still belong to the OnlineDay island.

## Safety rule
- route path stays the same
- response keys stay the same
- validation behavior stays the same
- mounted legacy path remains fallback when no SSOT queue mapping is resolved for the requested department/day

## In scope
- [queues.py](C:/final/backend/app/api/v1/endpoints/queues.py)
- [queue_stats_parity_harness.py](C:/final/backend/app/services/queue_stats_parity_harness.py)
- tests/docs for this slice

## Out of scope
- `board_state`
- `next_ticket`
- `open_day` / `close_day`
- OnlineDay model/service removal
- broader OnlineDay retirement
