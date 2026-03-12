# W2D board_state queue wiring

## What changed

The internal `BoardStateReadAdapter` now wires `queue_state` from the same
proven source direction already used by the `queues.stats` replacement work.

This is still internal-only wiring:

- no mounted `/board/state` switch
- no OpenAPI change
- no route behavior change

## Wired queue-state fields

The adapter now populates:

- `department`
- `date_str`
- `last_ticket`
- `waiting`
- `serving`
- `done`

## Accepted source shapes

The adapter now accepts:

- `QueuesStatsReplacementResult`
- `QueuesStatsSnapshot`
- snapshot-like objects with matching field names
- plain mappings with the same keys

That makes it compatible with the already-proven read artifact from:

- [queue_stats_parity_harness.py](C:/final/backend/app/services/queue_stats_parity_harness.py)

## What stayed outside queue_state

Still intentionally not part of `queue_state`:

- `is_open`
- `start_number`

These remain compatibility-only and continue to belong to the explicit
`compatibility` section of the adapter.

## Why this slice is safe

- no mounted route switch
- no queue-state logic mixed into `display_metadata`
- no product semantics changed
- no dependency on `next_ticket`, `open_day`, or `close_day`

## What still blocks mounted board_state replacement

- unresolved metadata ownership for `logo`, `is_paused`, `is_closed`,
  `contrast_default`, `kiosk_default`
- mounted route still has a request/consumer mismatch
- `is_open` and `start_number` still need compatibility handling
- no board-state parity/comparison harness exists yet for the fully wired
  adapter candidate
