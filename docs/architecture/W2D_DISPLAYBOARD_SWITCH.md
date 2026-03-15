## What Changed

`DisplayBoardUnified.jsx` now reads clean metadata fields through the new frontend adapter:

- `fetchBoardDisplayStateV1(boardKey)`

The page did not switch queue counters, websocket flow, or any admin/display producer surfaces.

## Metadata Fields Now Sourced From the New Adapter

The page now reads these fields from the new board-display endpoint path:

- `brand`
- `announcement`
- `announcement_ru`
- `announcement_uz`
- `announcement_en`
- `primary_color`
- `bg_color`
- `text_color`
- `sound_default`

## Compatibility Fallback That Remains

The page still uses compatibility fallback for:

- `logo`
- `is_paused`
- `is_closed`
- `contrast_default`
- `kiosk_default`

The current fallback source remains legacy `/api/v1/board/state`, with the existing local/default behavior preserved underneath it.

## What Stayed Untouched

This slice intentionally did not change:

- websocket board flow
- `/queues/stats`
- `/queue/queue/status`
- legacy `/api/v1/board/state` route ownership
- admin display settings/config producers

## Why This Switch Is Safe

This page switch is still staged and reversible because:

- only metadata fetching changed
- legacy route is still present
- unresolved fields still have compatibility fallback
- counters and websocket were left on their existing sources

## What Still Needs To Happen Before Broader Board Migration

The remaining board-metadata gap is now concentrated in unresolved fields:

- `logo`
- `is_paused`
- `is_closed`
- `contrast_default`
- `kiosk_default`

Those need either:

- adapter/backend extension with confirmed owners, or
- an explicit decision to keep them on compatibility fallback longer
