# W2D board_state adapter skeleton plan

## What the adapter should own

- internal assembly seam for future board-state replacement
- explicit separation between:
  - display metadata/config
  - queue/read-state inputs
  - compatibility fields

## What it should not own yet

- mounted `/board/state` behavior
- route switching
- final parity mapping for board metadata
- product decisions for pause/closed semantics

## Future input sources

- display metadata/config:
  - `DisplayBoard`
  - `DisplayAnnouncement`
  - related display-config CRUD/services
- queue/read-state inputs:
  - SSOT-backed read-model direction from `DailyQueue` / `OnlineQueueEntry`
- compatibility fields:
  - remaining OnlineDay-backed fields such as `is_open` and `start_number` if still needed

## First-skeleton response scope

Top-level internal sections only:
- `display_metadata`
- `queue_state`
- `compatibility`

The skeleton may expose typed fields for these sections, but it stays internal
and unmounted.

## Why this is safe

- no route switch
- no OpenAPI change
- no frontend contract change
- mounted [board.py](C:/final/backend/app/api/v1/endpoints/board.py) remains the source of truth for runtime behavior
