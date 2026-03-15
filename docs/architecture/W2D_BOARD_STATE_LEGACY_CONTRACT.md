# W2D board_state legacy contract

## Mounted endpoint

- Path: `GET /api/v1/board/state`
- Runtime owner: [board.py](C:/final/backend/app/api/v1/endpoints/board.py)
- Legacy service source: [online_queue.py](C:/final/backend/app/services/online_queue.py) `load_stats(...)`

## Current request contract

Required query params:
- `department`
- `date`

The endpoint currently requires both values and directly forwards them into the
OnlineDay legacy counter world.

## Current response shape

Current runtime payload is a plain queue-counter snapshot:

- `department`
- `date_str`
- `is_open`
- `start_number`
- `last_ticket`
- `waiting`
- `serving`
- `done`

## Semantic meaning of each field

- `department`
  - legacy department key echoed from request / OnlineDay identity
- `date_str`
  - request day in `YYYY-MM-DD`
- `is_open`
  - legacy OnlineDay day-state flag from [online.py](C:/final/backend/app/models/online.py)
- `start_number`
  - legacy OnlineDay starting ticket number
- `last_ticket`
  - legacy Setting-based issued ticket counter
- `waiting`
  - legacy Setting-based waiting count
- `serving`
  - legacy Setting-based serving count
- `done`
  - legacy Setting-based completed count

## What actually comes from OnlineDay vs legacy counters

From OnlineDay model:
- `is_open`
- `start_number`

From `Setting(category="queue")` counters:
- `last_ticket`
- `waiting`
- `serving`
- `done`

## What does not come from the current runtime contract

The mounted runtime does **not** provide any real board/display metadata:

- `brand`
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

Those fields are expected by the current UI consumer, but they are not part of
the actual runtime payload returned by [board.py](C:/final/backend/app/api/v1/endpoints/board.py).

## UI-critical vs legacy-only

UI-critical for the current display page:
- board/display metadata listed above

Legacy-only in the current `board_state()` payload:
- `department`
- `date_str`
- `is_open`
- `start_number`
- `last_ticket`
- `waiting`
- `serving`
- `done`

Those counter fields are real runtime output, but the current UI does not use
them from `/board/state`; it reads counters from `/queues/stats` instead.
