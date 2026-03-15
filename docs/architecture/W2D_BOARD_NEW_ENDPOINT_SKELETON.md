# W2D board new endpoint skeleton

## What was added

An additive public endpoint skeleton was added for the future board-display
contract:

- `GET /api/v1/display/boards/{board_key}/state`

Mounted owner:

- [board_display_state.py](C:/final/backend/app/api/v1/endpoints/board_display_state.py)

Composition owner:

- [board_state_read_adapter.py](C:/final/backend/app/services/board_state_read_adapter.py)

## What the skeleton exposes

Current mounted v1 payload:

- `board_key`
- `display_metadata.brand`
- `display_metadata.announcement`
- `display_metadata.announcement_ru`
- `display_metadata.announcement_uz`
- `display_metadata.announcement_en`
- `display_metadata.primary_color`
- `display_metadata.bg_color`
- `display_metadata.text_color`
- `display_metadata.sound_default`

## What it does not expose

Still deferred from the mounted skeleton:

- `queue_state`
- `logo`
- `is_paused`
- `is_closed`
- `contrast_default`
- `kiosk_default`
- legacy compatibility fields such as `is_open` and `start_number`

## Why this is safe

- additive endpoint only
- no legacy route mutation
- no frontend switch
- no queue-state mixing in v1
- no attempt to solve unresolved display ownership in the same slice

## Data ownership in the current skeleton

Current metadata sources:

- `brand` from `DisplayBoard.display_name` or `name`
- `announcement*` from `DisplayAnnouncement` flattening in adapter composition
- `primary_color`, `bg_color`, `text_color` from `DisplayBoard.colors`
- `sound_default` from `DisplayBoard.sound_enabled`

## Legacy route status

[board.py](C:/final/backend/app/api/v1/endpoints/board.py) remains unchanged.

Legacy `/api/v1/board/state` is still the OnlineDay-backed counter route and is
not affected by this skeleton.

