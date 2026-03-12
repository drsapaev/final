## Scope

This slice switches only `DisplayBoardUnified.jsx` metadata loading to the new frontend adapter for:

- `GET /api/v1/display/boards/{board_key}/state`

In scope:

- `frontend/src/pages/DisplayBoardUnified.jsx`
- `frontend/src/api/boardDisplay.js` only if tiny helper support is needed
- focused frontend tests
- slice documentation/status

Out of scope:

- websocket logic
- queue counters
- `/queues/stats`
- `/queue/queue/status`
- admin display settings pages
- legacy `/api/v1/board/state` removal

## Metadata Fields Switching Now

These fields should move to the new adapter:

- `brand`
- `announcement`
- `announcement_ru`
- `announcement_uz`
- `announcement_en`
- `primary_color`
- `bg_color`
- `text_color`
- `sound_default`

## Compatibility Fallback Fields

These fields remain on compatibility fallback:

- `logo`
- `is_paused`
- `is_closed`
- `contrast_default`
- `kiosk_default`

## Fallback Strategy

The page should:

- try the new adapter first for clean metadata fields
- keep legacy `/board/state` available only for unresolved fields
- preserve existing default behavior if both remote paths fail
- keep current localStorage/default fallbacks compatible with the existing page behavior

## Why This Slice Is Safe

This slice is safe because:

- websocket flow remains untouched
- counters remain untouched
- the adapter is already present and tested
- the page switch is limited to metadata loading only
- legacy `/board/state` remains available as rollback/compatibility support
