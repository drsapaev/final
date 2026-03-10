# W2D board_state consumer usage

## Confirmed current consumer

Confirmed live consumer:
- [DisplayBoardUnified.jsx](C:/final/frontend/src/pages/DisplayBoardUnified.jsx)

Current call site:
- `api.get('/board/state')`

Important runtime note:
- the current consumer does **not** send the required `department` and `date`
  query params when calling `/board/state`
- the request therefore falls into the component `catch` path, which then uses
  local cache or hard-coded defaults

## Field and section usage map

| Field / Section | Used by current UI | Where used | Required for first replacement | Can remain on compatibility fallback |
| --- | --- | --- | --- | --- |
| `department` | No | Not read from `board_state` consumer path | No | Yes |
| `date_str` | No | Not read from `board_state` consumer path | No | Yes |
| `is_open` | No | Not used by `DisplayBoardUnified` | No | Yes |
| `start_number` | No | Not used by `DisplayBoardUnified` | No | Yes |
| `last_ticket` | No | Counters come from `/queues/stats`, not `/board/state` | No | Yes |
| `waiting` | No | Counters come from `/queues/stats`, not `/board/state` | No | Yes |
| `serving` | No | Counters come from `/queues/stats`, not `/board/state` | No | Yes |
| `done` | No | Counters come from `/queues/stats`, not `/board/state` | No | Yes |
| `brand` / `title` | Yes | Header branding in `DisplayBoardUnified` | Yes | No |
| `logo` / `logo_url` | Yes | Header logo in `DisplayBoardUnified` | Yes | No |
| `is_paused` / `paused` | Yes | Pause banner logic | Yes | No |
| `is_closed` / `closed` | Yes | Closed banner logic | Yes | No |
| `announcement` | Yes | Fallback announcement ticker | Yes | No |
| `announcement_ru` / `announcement_uz` / `announcement_en` | Yes | Language-specific ticker | Yes | No |
| `primary_color` / `bg_color` / `text_color` | Yes | Theme and surface colors | Yes | No |
| `contrast_default` | Yes | Initial accessibility/display defaults | Yes | No |
| `kiosk_default` | Yes | Initial board mode defaults | Yes | No |
| `sound_default` | Yes | Initial sound mode default | Yes | No |

## Adjacent board/display data that does not come from board_state

The page gets other live board content from separate sources:

- `/queues/stats`
  - counter feed for `last_ticket`, `waiting`, `serving`, `done`
- display WebSocket
  - queue entries
  - current calls
  - announcement stream
- `/queue/queue/status`
  - cabinet/window state

## Practical implication

For the current UI, `board_state` is effectively a display-metadata endpoint,
not a counter endpoint, even though the mounted runtime still returns only
legacy queue counters.
