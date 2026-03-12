# W2D board_state display wiring

## What changed

The internal `BoardStateReadAdapter` now wires confirmed display metadata
sources from the display-config domain, while the mounted
[board.py](C:/final/backend/app/api/v1/endpoints/board.py) route stays fully
legacy and unchanged.

Wired now:

- `brand`
- `primary_color`
- `bg_color`
- `text_color`
- `sound_default`
- `announcement`
- `announcement_ru`
- `announcement_uz`
- `announcement_en`

## Current adapter source ownership

### DisplayBoard-backed fields

From [display_config.py](C:/final/backend/app/models/display_config.py):

- `brand` <- `DisplayBoard.display_name` with fallback to `DisplayBoard.name`
- `primary_color` <- `DisplayBoard.colors["primary"]`
- `bg_color` <- `DisplayBoard.colors["background"]`
- `text_color` <- `DisplayBoard.colors["text"]`
- `sound_default` <- `DisplayBoard.sound_enabled`

### DisplayAnnouncement-backed fields

From `DisplayAnnouncement`-like records:

- `announcement`
- `announcement_ru`
- `announcement_uz`
- `announcement_en`

Current adapter behavior:

- only active announcements are considered
- highest-priority active announcement becomes generic `announcement`
- language-specific flat fields are filled from the first highest-priority
  active record per language

## What remained unresolved

Still intentionally unresolved in this slice:

- `logo`
- `is_paused`
- `is_closed`
- `contrast_default`
- `kiosk_default`

These remain explicit placeholders in the adapter because their ownership is
still missing or not replacement-ready.

## Why this slice is safe

- no mounted route switch
- no OpenAPI change
- no frontend behavior change
- no queue-state wiring mixed into metadata wiring
- no change to legacy `/board/state` response contract

## What still blocks mounted replacement

- unresolved ownership for pause/closed/config fields
- unresolved board-logo read ownership
- current mounted route contract still mismatches live UI calls
- queue-state inputs are not yet wired into the adapter
- compatibility-only fields `is_open` and `start_number` still need legacy
  handling
