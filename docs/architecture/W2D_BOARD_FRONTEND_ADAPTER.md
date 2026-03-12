## What Was Added

A thin frontend adapter layer for the new additive backend endpoint:

- `GET /api/v1/display/boards/{board_key}/state`

Implementation artifacts:

- `frontend/src/api/endpoints.js`
- `frontend/src/api/boardDisplay.js`
- `frontend/src/api/index.js`

## Adapter Ownership

The new adapter is intentionally narrow.

It owns:

- the new board-display endpoint path
- normalization of the metadata-only v1 response
- exposure of only the fields that map cleanly today

It does not own:

- legacy `/board/state`
- page-level fallback behavior
- websocket state
- queue counters
- unresolved display fields

## Supported Fields

The adapter currently exposes:

- `boardKey`
- `brand`
- `announcement`
- `announcement_ru`
- `announcement_uz`
- `announcement_en`
- `primary_color`
- `bg_color`
- `text_color`
- `sound_default`

These fields come directly from the new metadata-only v1 endpoint contract.

## Deferred Fields

The adapter intentionally does not fabricate or normalize:

- `logo`
- `is_paused`
- `is_closed`
- `contrast_default`
- `kiosk_default`

These remain deferred for the later frontend switch, where a compatibility fallback can still keep current UI behavior stable.

## Why This Slice Is Safe

This slice is safe because:

- no live page switched to the new adapter
- legacy `/board/state` remains mounted and untouched
- existing queue counter and websocket paths are untouched
- the adapter is fully additive and test-covered

## What This Enables Next

The next narrow frontend slice can now focus on:

- switching `DisplayBoardUnified.jsx` to the new adapter
- keeping unresolved fields on compatibility fallback
- preserving rollback simplicity because the old route remains intact
