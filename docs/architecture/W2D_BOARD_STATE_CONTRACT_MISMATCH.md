# W2D board_state contract mismatch

## Current legacy route

Mounted route:

- `GET /api/v1/board/state`
- owner: [board.py](C:/final/backend/app/api/v1/endpoints/board.py)
- legacy source: [online_queue.py](C:/final/backend/app/services/online_queue.py)

Current request contract:

- requires `department`
- requires `date`

Current response contract:

- `department`
- `date_str`
- `is_open`
- `start_number`
- `last_ticket`
- `waiting`
- `serving`
- `done`

Semantically this is an OnlineDay-era queue counter snapshot, not a board display
state payload.

## What the live UI actually expects

Confirmed consumer:

- [DisplayBoardUnified.jsx](C:/final/frontend/src/pages/DisplayBoardUnified.jsx)

The page effectively expects a display-oriented payload:

- `brand` or `title`
- `logo` or `logo_url`
- `is_paused` or `paused`
- `is_closed` or `closed`
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

The current UI does not rely on `/board/state` for queue counters. It gets
counter-like data from:

- [queues.py](C:/final/backend/app/api/v1/endpoints/queues.py) `stats()`
- display WebSocket state
- [DisplayBoardUnified.jsx](C:/final/frontend/src/pages/DisplayBoardUnified.jsx)
  local defaults / cache fallback

## Exact mismatch

### 1. Request mismatch

Legacy route requires `department` and `date`.

The live UI calls:

- `api.get('/board/state')`

without those required query params.

So the mounted contract and the live call pattern do not match even before the
response body is considered.

### 2. Response-shape mismatch

Legacy route returns queue counters only.

Live UI expects display metadata and board-config defaults.

There is almost no meaningful overlap except the broad concept of "board state".

### 3. Ownership mismatch

Legacy owner:

- OnlineDay counter world

Likely future owner:

- display-config domain plus SSOT-backed queue read inputs

These are different domains with different data ownership.

## What overlap does exist

There is limited overlap only if a future board payload still wants queue
summary fields:

- `department`
- `date_str`
- `last_ticket`
- `waiting`
- `serving`
- `done`

But even those fields are no longer UI-critical inside the current board page,
because the page already reads them from other sources.

## What is currently satisfied only by defaults or fallbacks

Because the mounted route does not satisfy the UI contract, the live page
currently relies on local defaults, cache fallback, or independent data sources
for:

- branding
- colors
- announcements
- pause/closed flags
- board mode defaults

## Architectural conclusion

The blocker is no longer data parity for counters. The blocker is that
`/board/state` currently means "legacy queue counter snapshot", while the live
UI uses the same route name as if it meant "display-board metadata payload".
