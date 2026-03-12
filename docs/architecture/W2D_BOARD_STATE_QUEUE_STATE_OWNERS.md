# W2D board_state queue_state owners

## Summary

`board_state` queue counters should not invent a new queue source. The safest
future owner is the same SSOT-backed read-model direction already established
for [queues.py](C:/final/backend/app/api/v1/endpoints/queues.py) `stats()`.

This means the `queue_state` part of `BoardStateReadAdapter` should reuse the
same department/day aggregate logic over:

- `DailyQueue`
- `OnlineQueueEntry`
- department/day mapping through queue-profile and doctor/department relations

## Field owner map

| Queue-state field | Current legacy owner | Future SSOT owner | Parity confidence | Replacement-ready |
| --- | --- | --- | --- | --- |
| `department` | Request echo + OnlineDay context in [board.py](C:/final/backend/app/api/v1/endpoints/board.py) | Adapter/request context echo | High | Yes |
| `date_str` | Legacy request/date formatting in [board.py](C:/final/backend/app/api/v1/endpoints/board.py) | Adapter/request context echo | High | Yes |
| `last_ticket` | Legacy counters from OnlineDay island via [online_queue.py](C:/final/backend/app/services/online_queue.py) | SSOT queue-stats read-model direction in [queue_stats_parity_harness.py](C:/final/backend/app/services/queue_stats_parity_harness.py) | High | Yes |
| `waiting` | Legacy `Setting(category=\"queue\")` counter path | SSOT queue-stats read-model direction | High | Yes |
| `serving` | Legacy `Setting(category=\"queue\")` counter path | SSOT queue-stats read-model direction | High | Yes |
| `done` | Legacy `Setting(category=\"queue\")` counter path | SSOT queue-stats read-model direction | High | Yes |

## Proven future owner direction

The queues.stats replacement already established that strict consumer-visible
counters can be SSOT-backed where department/day mapping resolves safely.

Evidence:

- [W2D_QUEUES_STATS_REPLACEMENT.md](C:/final/docs/architecture/W2D_QUEUES_STATS_REPLACEMENT.md)
- [queue_stats_parity_harness.py](C:/final/backend/app/services/queue_stats_parity_harness.py)

That makes `queue_state` the *least controversial* part of future board-state
wiring. The main uncertainty is not counters themselves, but how much of that
counter block still belongs in `board_state` once display metadata is wired.

## Mapping assumptions

The future adapter should reuse the same mapping assumptions already accepted
for `queues.stats`:

- department/day input drives the aggregate
- `DailyQueue` + `OnlineQueueEntry` provide strict counters
- legacy fallback remains necessary only for compatibility-only fields, not for
  `last_ticket`, `waiting`, `serving`, `done`

## Wiring implication

`queue_state` is technically more replacement-ready than the metadata block, but
it is not the first wiring priority because:

- the current live UI does not rely on `board_state` for counters
- the current live UI already reads counters from `/queues/stats`
- the more urgent board-state problem is metadata ownership, not counter parity

## Current slice status

The internal adapter now wires queue-state fields from the same proven source
direction used by the `queues.stats` replacement work.

Wired now:

- `department`
- `date_str`
- `last_ticket`
- `waiting`
- `serving`
- `done`

Accepted adapter inputs:

- `QueuesStatsReplacementResult`
- `QueuesStatsSnapshot`
- snapshot-like objects with the same field names

Implementation evidence:

- [board_state_read_adapter.py](C:/final/backend/app/services/board_state_read_adapter.py)
- [test_board_state_queue_wiring.py](C:/final/backend/tests/unit/test_board_state_queue_wiring.py)

Still intentionally outside `queue_state`:

- `is_open`
- `start_number`

These remain in the separate `compatibility` section only.
