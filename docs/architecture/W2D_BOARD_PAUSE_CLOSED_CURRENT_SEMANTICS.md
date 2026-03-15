# W2D board pause/closed current semantics

## Evidence summary

Current live backend legacy route [board.py](C:/final/backend/app/api/v1/endpoints/board.py)
returns only:

- `department`
- `date_str`
- `is_open`
- `start_number`
- `last_ticket`
- `waiting`
- `serving`
- `done`

It does **not** return `is_paused` or `is_closed`.

Current live frontend consumer
[DisplayBoardUnified.jsx](C:/final/frontend/src/pages/DisplayBoardUnified.jsx)
still reads:

- `source.is_paused || source.paused`
- `source.is_closed || source.closed`

from the compatibility source in `buildBoardState(...)`.

## `is_paused`

- current source:
  - no confirmed mounted backend source
  - can only come from compatibility payloads, cached board state, or mocked test
    payloads
- runtime meaning:
  - show the paused banner on the board page
  - only applies when `is_closed` is false
- UI meaning:
  - display-only operational banner: "Работа приостановлена"
- display-domain or queue-domain:
  - display-domain / operational presentation state
  - not a queue counter and not a websocket concern
- explicit or accidental:
  - currently accidental / compatibility-only
  - no explicit backend owner is present in the mounted board-display path

## `is_closed`

- current source:
  - no confirmed mounted backend source
  - can only come from compatibility payloads, cached board state, or mocked test
    payloads
- runtime meaning:
  - show the closed banner on the board page
  - takes precedence over paused banner
- UI meaning:
  - display-only operational banner: "Клиника закрыта"
- display-domain or queue-domain:
  - display-domain / operational presentation state
  - not part of queue counters returned by the legacy OnlineDay board route
- explicit or accidental:
  - currently accidental / compatibility-only
  - there is no confirmed backend owner in the mounted board-display path

## Important distinction

These fields are not the same thing as:

- OnlineDay `is_open`
- queue open/closed state
- queue websocket connectivity
- queue counters

The current board page treats them as presentation banners, not as allocator or
queue lifecycle state.
