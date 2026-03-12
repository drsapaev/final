# W2D board_state parity harness plan

## Goal

Build a non-invasive legacy-vs-adapter comparison harness for `board_state`
before any mounted replacement discussion.

## Harness inputs

The harness will take:

- `db`
- `department`
- `date_str`
- optional `display_board`
- optional `display_announcements`

## Legacy path read

Legacy source of truth remains:

- mounted route contract from [board.py](C:/final/backend/app/api/v1/endpoints/board.py)
- underlying legacy stats owner [online_queue.py](C:/final/backend/app/services/online_queue.py)

For harness safety, legacy payload will be reconstructed from the same backend
logic as the mounted route, without switching the route itself.

## Adapter path read

Candidate source will be:

- [board_state_read_adapter.py](C:/final/backend/app/services/board_state_read_adapter.py)

Its queue-state section will be fed from the already-proven `queues.stats`
replacement direction:

- [queue_stats_parity_harness.py](C:/final/backend/app/services/queue_stats_parity_harness.py)

## Strict parity fields

Strict queue-state parity fields:

- `department`
- `date_str`
- `last_ticket`
- `waiting`
- `serving`
- `done`

## Compatibility-only / deferred fields

Compatibility-only:

- `is_open`
- `start_number`

Deferred / unresolved display fields:

- `logo`
- `is_paused`
- `is_closed`
- `contrast_default`
- `kiosk_default`

## Display-metadata comparison rule

Display metadata is only comparable where comparison is actually meaningful.
Because the legacy mounted route does not expose board metadata, the harness
should:

- compare queue-state parity strictly
- compare compatibility fields separately
- record metadata fields as `non-comparable/deferred` instead of forcing false
  parity claims

## Why this is safe

- no mounted route switch
- no OpenAPI change
- no runtime contract change
- legacy route remains source of truth during the comparison phase
