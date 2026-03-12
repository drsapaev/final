# W2D OnlineDay Board/Stats Response Gaps

## Current Legacy Contracts

### `GET /api/v1/queues/stats`

Current payload is `asdict(DayStats)`:

- `department`
- `date_str`
- `is_open`
- `start_number`
- `last_ticket`
- `waiting`
- `serving`
- `done`

### `GET /api/v1/appointments/stats`

Current payload is effectively the same `DayStats` contract, hand-built in the endpoint:

- `department`
- `date_str`
- `is_open`
- `start_number`
- `last_ticket`
- `waiting`
- `serving`
- `done`

### `GET /api/v1/board/state`

Current runtime payload is also the same counter payload:

- `department`
- `date_str`
- `is_open`
- `start_number`
- `last_ticket`
- `waiting`
- `serving`
- `done`

## Consumer / Response Reality

### `queues.stats`

- Confirmed live consumer: `DisplayBoardUnified.jsx`
- The consumer uses it as the actual queue counter feed

### `appointments.stats`

- No confirmed frontend product consumer found in `frontend/src`
- Only generic API wrapper remains in `frontend/src/api/services.js`
- This makes it a likely retire-or-redirect candidate, not the first replacement target

### `board.state`

- Confirmed live consumer: `DisplayBoardUnified.jsx`
- But the UI expects more than the runtime provides:
  - `brand`
  - `logo`
  - `is_paused`
  - `is_closed`
  - announcements
  - color defaults
- Current runtime `board.state()` does not provide those fields; the UI falls back to defaults/local cache
- Older documentation also describes a richer board payload than runtime actually serves

## Main Gaps Blocking Replacement

1. No SSOT department/day aggregate exists yet
   - current SSOT reads are queue/specialist oriented
2. No SSOT equivalent exists yet for legacy counters
   - especially `start_number` and `last_ticket`
3. `board.state()` is not just a stats question
   - it needs a display-state adapter, not just a queue counter projection
4. `appointments.stats()` has unclear consumer value
   - replacement should not start there

## Implication

The safest first replacement target is the narrowest confirmed live counter surface:
`queues.stats()`.

Replacing `board.state()` first would require solving both:

- queue counter projection
- board/display metadata contract

That is broader than the smallest safe first slice.
