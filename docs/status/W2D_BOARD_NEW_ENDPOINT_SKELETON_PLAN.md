# W2D board new endpoint skeleton plan

## Files in scope

Code:

- [api.py](C:/final/backend/app/api/v1/api.py)
- new public endpoint module under
  [endpoints](C:/final/backend/app/api/v1/endpoints)
- [board_state_read_adapter.py](C:/final/backend/app/services/board_state_read_adapter.py)
  only if a narrow endpoint-facing helper is useful
- focused tests under
  [backend/tests/unit](C:/final/backend/tests/unit)
  and
  [backend/tests/integration](C:/final/backend/tests/integration)

Docs:

- [W2D_BOARD_NEW_ENDPOINT_SKELETON.md](C:/final/docs/architecture/W2D_BOARD_NEW_ENDPOINT_SKELETON.md)
- [W2D_BOARD_NEW_ENDPOINT_SKELETON_STATUS.md](C:/final/docs/status/W2D_BOARD_NEW_ENDPOINT_SKELETON_STATUS.md)
- [W2D_BOARD_NEW_ENDPOINT_RESPONSE.md](C:/final/docs/architecture/W2D_BOARD_NEW_ENDPOINT_RESPONSE.md)
- [W2D_BOARD_NEW_ENDPOINT_MIGRATION_STRATEGY.md](C:/final/docs/architecture/W2D_BOARD_NEW_ENDPOINT_MIGRATION_STRATEGY.md)
- [W2D_NEXT_EXECUTION_UNIT_AFTER_BOARD_NEW_ENDPOINT_SKELETON.md](C:/final/docs/status/W2D_NEXT_EXECUTION_UNIT_AFTER_BOARD_NEW_ENDPOINT_SKELETON.md)

## Mounted path shape

Planned additive route:

- `GET /api/v1/display/boards/{board_key}/state`

Where:

- `board_key` maps to `DisplayBoard.name`

## Response shape

Mounted skeleton should expose only metadata-first v1 fields:

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

## Confirmed v1-only scope

Will not expose in this slice:

- `queue_state`
- `is_open`
- `start_number`
- `logo`
- `is_paused`
- `is_closed`
- `contrast_default`
- `kiosk_default`

## Why this slice is safe

- additive route only
- legacy `/board/state` remains untouched
- no frontend switch
- uses already-established adapter ownership direction
- limits mounted contract to fields with the clearest current owners

## Why legacy route remains untouched

The legacy route still belongs to the OnlineDay island and carries a different
contract meaning. This slice adds a new public surface rather than mutating that
meaning in place.
