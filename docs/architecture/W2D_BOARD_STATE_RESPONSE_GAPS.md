# W2D board_state response gaps

## Current legacy response contract

Mounted [board.py](C:/final/backend/app/api/v1/endpoints/board.py) returns only:

- `department`
- `date_str`
- `is_open`
- `start_number`
- `last_ticket`
- `waiting`
- `serving`
- `done`

## Current consumer expectation

[DisplayBoardUnified.jsx](C:/final/frontend/src/pages/DisplayBoardUnified.jsx) expects a much richer board payload:

- `brand` / `title`
- `logo` / `logo_url`
- `is_paused` / `paused`
- `is_closed` / `closed`
- `announcement`
- `announcement_ru`
- `announcement_uz`
- `announcement_en`
- `primary_color`
- `bg_color`
- `text_color`
- `contrast_default`
- `kiosk_default`
- `sound_default`

## Major mismatch categories

### 1. Request mismatch

Current endpoint requires:
- `department`
- `date`

Current UI call does not provide them.

Result:
- the request fails
- UI falls back to local cache/default values

### 2. Counter-vs-metadata mismatch

Current runtime returns queue counters.
Current UI expects board/display metadata.

That means the mounted route name is not aligned with the actual consumer role.

### 3. Missing backend owner for critical fields

No clear backend owner was found for:
- `is_paused`
- `is_closed`
- `contrast_default`
- `kiosk_default`

These are currently UI-expected fields without a proven runtime source.

### 4. Partial display-config overlap, not full parity

The backend does already have a display-config domain:
- [display_config.py](C:/final/backend/app/models/display_config.py)
- [crud/display_config.py](C:/final/backend/app/crud/display_config.py)

This can plausibly own:
- display name / board identity
- sound defaults
- colors
- announcement records

But it does not yet prove parity for the current `board_state` consumer contract.

### 5. Announcement model mismatch

Current UI expects board-level flat announcement fields.
Display-config domain stores announcements as records with:
- `title`
- `message`
- `language`
- `priority`

So a translation/flattening adapter would still be needed.

### 6. Counter inclusion decision still open

If future `board_state` keeps queue counters, those counters should likely come
from the same SSOT read-model direction already used for `queues.stats`.

But counters are not the first consumer-visible reason the current page calls
`board_state`.

## What blocks direct replacement today

- no proven parity source for UI-critical board metadata
- no proven owner for pause/closed state
- current route request contract does not match current consumer usage
- announcement/config mapping still needs an adapter layer
