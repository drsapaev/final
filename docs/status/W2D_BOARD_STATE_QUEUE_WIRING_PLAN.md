# W2D board_state queue wiring plan

## Scope of this slice

This slice wires only the `queue_state` section of the internal
`BoardStateReadAdapter`, using the already-proven SSOT-backed direction from
the `queues.stats` replacement work.

## Queue-state fields to wire now

The following fields can be wired safely:

- `department`
- `date_str`
- `last_ticket`
- `waiting`
- `serving`
- `done`

## Safe source for this slice

The adapter should accept the same proven replacement artifact already used by
[queues.py](C:/final/backend/app/api/v1/endpoints/queues.py):

- `QueuesStatsReplacementResult.snapshot`
- or directly `QueuesStatsSnapshot`

Source implementation:

- [queue_stats_parity_harness.py](C:/final/backend/app/services/queue_stats_parity_harness.py)

## Fields that must stay outside queue_state

These remain explicit compatibility-only fields and must not be folded into
`queue_state`:

- `is_open`
- `start_number`

They continue to belong to the `compatibility` section only.

## Safety rationale

This slice is safe because:

- it does not switch mounted `/board/state`
- it does not change OpenAPI or route behavior
- it does not touch `next_ticket`, `open_day`, or `close_day`
- it reuses an already validated SSOT-backed read direction instead of
  inventing a new queue source

## In scope

- [board_state_read_adapter.py](C:/final/backend/app/services/board_state_read_adapter.py)
- unit tests for adapter queue-state wiring
- wiring/status docs

## Out of scope

- mounted route replacement
- display metadata redesign
- compatibility-field cutover
- broad queue read-model refactor
