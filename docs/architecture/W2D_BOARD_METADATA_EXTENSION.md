# W2D board metadata extension

## Scope

This slice extended the additive board-display endpoint and staged
`DisplayBoardUnified.jsx` switch only for the unresolved metadata fields that
had sufficiently confirmed backend ownership.

In scope:

- `logo`
- `contrast_default`
- `kiosk_default`

Out of scope:

- `is_paused`
- `is_closed`
- `queue_state`
- websocket flow
- legacy `/api/v1/board/state` removal

## What moved successfully

The new adapter-backed endpoint now exposes:

- `display_metadata.logo`
- `display_metadata.contrast_default`
- `display_metadata.kiosk_default`

`DisplayBoardUnified.jsx` now prefers those fields from the new board-display
adapter, while keeping the existing compatibility path intact for unresolved
metadata.

## Current backend ownership

- `logo`
  - primary owner: `Setting(category="display_board", key="logo")`
  - compatibility fallback: clinic `logo_url` if display-board logo is absent
- `contrast_default`
  - owner: `Setting(category="display_board", key="contrast_default")`
- `kiosk_default`
  - owner: `Setting(category="display_board", key="kiosk_default")`

## What remains on legacy fallback

These fields still remain on compatibility fallback in
`DisplayBoardUnified.jsx`:

- `is_paused`
- `is_closed`

Reason: there is still no confirmed backend owner with stable semantics for
those values in the new board-display contract.

## Outcome

The board page is now mostly off legacy `/board/state` for metadata reads:

- adapter-backed:
  - `brand`
  - `logo`
  - `announcement*`
  - `primary_color`
  - `bg_color`
  - `text_color`
  - `contrast_default`
  - `kiosk_default`
  - `sound_default`
- legacy compatibility only:
  - `is_paused`
  - `is_closed`

The legacy route also remains as a full rollback path if the new adapter call
fails.
