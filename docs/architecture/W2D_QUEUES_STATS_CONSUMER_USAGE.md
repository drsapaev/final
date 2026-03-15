# W2D Queues Stats Consumer Usage

## Confirmed Consumers

### Primary confirmed consumer

- `frontend/src/pages/DisplayBoardUnified.jsx`

This component calls the legacy endpoint directly:

- `api.get('/queues/stats', { query: qs })`

It does not go through the generic `queueService.getQueueStats()` wrapper.

### Secondary / indirect wrappers

- `frontend/src/api/services.js`
  - `queueService.getQueueStats(params = {})`
  - `appointmentsService.getAppointmentsStats(params = {})`

These wrappers exist, but no confirmed current `frontend/src` caller was found for
either wrapper in this replacement-prep slice.

## Field Usage Map

| Field | Used by confirmed consumer? | Where used | Required for initial replacement? | Can be deprecated later? |
| --- | --- | --- | --- | --- |
| `department` | No confirmed response usage | Request query is built from `department`, but response field is not read | No | Yes |
| `date_str` | No confirmed response usage | Not read in `DisplayBoardUnified.jsx` | No | Yes |
| `is_open` | No confirmed `queues.stats` usage | Open/closed UI comes from `/board/state`, not `queues.stats` | No | Yes, if board replacement handles visibility separately |
| `start_number` | No confirmed usage | Not read in `DisplayBoardUnified.jsx` | No | Yes, pending business sign-off |
| `last_ticket` | Yes | "Now serving" fallback block and beep delta logic | Yes | No, not for first replacement |
| `waiting` | Yes | Legacy counter card | Yes | No, not for first replacement |
| `serving` | Yes | Legacy counter card | Yes | No, not for first replacement |
| `done` | Yes | Legacy counter card | Yes | No, not for first replacement |

## Important Consumer Observations

### `DisplayBoardUnified.jsx`

`queues.stats` is used for:

- `stats.last_ticket`
  - sound delta / last-ticket change detection
  - visible fallback "now serving" number when no live call is active
- `stats.waiting`
  - visible legacy waiting card
- `stats.serving`
  - visible legacy serving card
- `stats.done`
  - visible legacy done card

It is not used for:

- `stats.department`
- `stats.date_str`
- `stats.start_number`
- `stats.is_open`

### `board.state` Is Separate

The same page also calls `/board/state`, and that is where it currently expects
board-facing flags and metadata such as:

- brand / logo
- closed / paused state
- announcements
- colors

That separation is why `queues.stats` is the safest first replacement target: it
does not require solving board metadata ownership at the same time.

### Generic Wrapper Drift

`frontend/src/api/endpoints.js` still declares:

- `QUEUE.STATS = '/queue/stats'`

while the live legacy endpoint in mounted runtime is:

- `/queues/stats`

Because `DisplayBoardUnified.jsx` calls `/queues/stats` directly, the initial
replacement should preserve the mounted runtime path first and treat wrapper
cleanup as a later concern.

## Initial Replacement Implication

The first replacement slice only needs to preserve the confirmed consumer-visible
counter contract:

- `last_ticket`
- `waiting`
- `serving`
- `done`

The remaining fields should stay present for compatibility unless and until a later
redirect/retire decision is made.
