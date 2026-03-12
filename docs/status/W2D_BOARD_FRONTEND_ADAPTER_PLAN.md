## Scope

This slice adds only a thin frontend adapter/service layer for the new backend endpoint:

- `GET /api/v1/display/boards/{board_key}/state`

In scope:

- `frontend/src/api/endpoints.js`
- `frontend/src/api/boardDisplay.js`
- `frontend/src/api/index.js`
- frontend adapter tests
- slice documentation/status

Out of scope:

- switching `DisplayBoardUnified.jsx`
- removing legacy `/board/state`
- websocket changes
- queue counter changes
- broader page refactor

## Adapter Functions To Add

The adapter layer should provide:

- a dedicated endpoint constant for the new board-display route
- a fetch helper for board-display metadata v1
- a narrow normalization helper for the cleanly mapped metadata fields

## First Adapter Version: Supported Fields

The first adapter version should expose only fields that map cleanly from the new metadata-only backend contract:

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

## Deferred / Compatibility-Only Fields

These fields remain unresolved in this slice and must not be silently invented by the adapter:

- `logo`
- `is_paused`
- `is_closed`
- `contrast_default`
- `kiosk_default`

## Normalization Rules

The adapter should:

- read from the new additive backend route
- unwrap the metadata-first response shape
- flatten only the confirmed metadata v1 fields into a simple frontend-friendly object
- avoid manufacturing legacy-only fields

## Why This Slice Is Safe

This slice is non-invasive because:

- no live page switches to the new adapter yet
- legacy `/board/state` remains the current runtime source for the page
- the adapter only prepares the future frontend migration seam
- the adapter contract stays narrow and testable
