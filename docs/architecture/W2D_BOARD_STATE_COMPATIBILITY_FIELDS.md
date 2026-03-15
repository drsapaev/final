# W2D board_state compatibility fields

## Current compatibility-only fields

For the future `BoardStateReadAdapter`, the following fields still need to stay
legacy-backed / compatibility-only:

- `is_open`
- `start_number`

These are already modeled separately in the adapter skeleton:

- [board_state_read_adapter.py](C:/final/backend/app/services/board_state_read_adapter.py)

## Why these fields are compatibility-only

### `is_open`

Legacy source:

- OnlineDay day-state in [online.py](C:/final/backend/app/models/online.py)
- legacy runtime owner [online_queue.py](C:/final/backend/app/services/online_queue.py)

Why not SSOT-owned yet:

- no SSOT replacement for department/day open-close state has been defined
- this belongs to the separate OnlineDay retirement track, not to board-state
  wiring itself

Consumer-critical:

- not confirmed as a current live UI requirement for
  [DisplayBoardUnified.jsx](C:/final/frontend/src/pages/DisplayBoardUnified.jsx)

### `start_number`

Legacy source:

- OnlineDay / queue settings legacy counter world

Why not SSOT-owned yet:

- there is no agreed SSOT equivalent for legacy department/day start numbering
- current queues.stats replacement already deferred this field as compatibility
  fallback

Consumer-critical:

- not confirmed as a current live UI requirement for
  [DisplayBoardUnified.jsx](C:/final/frontend/src/pages/DisplayBoardUnified.jsx)

## Important distinction

`Compatibility-only` here does **not** mean all unresolved board-state fields.
It applies specifically to fields that:

- already exist in the legacy mounted contract
- still need to be carried temporarily
- do not yet have a safe SSOT owner

That is a different category from metadata fields such as:

- `is_paused`
- `is_closed`
- `logo`
- `contrast_default`
- `kiosk_default`

Those are not temporary compatibility fields. They are unresolved metadata
ownership problems.
