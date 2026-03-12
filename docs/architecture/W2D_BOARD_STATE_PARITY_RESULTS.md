# W2D board_state parity results

## Proven parity

The new comparison harness proves parity for the queue/counter portion of the
candidate adapter payload against the mounted legacy route.

Proven strict parity:

- `department`
- `date_str`
- `last_ticket`
- `waiting`
- `serving`
- `done`

Proven compatibility parity:

- `is_open`
- `start_number`

Evidence:

- [board_state_parity_harness.py](C:/final/backend/app/services/board_state_parity_harness.py)
- [test_board_state_parity_harness.py](C:/final/backend/tests/characterization/test_board_state_parity_harness.py)

## Non-comparable / deferred sections

The harness also proves that display metadata is **not** comparable against the
legacy mounted contract, because current mounted `/board/state` simply does not
expose those fields.

Non-comparable display fields observed in candidate adapter output:

- `brand`
- `announcement`
- `announcement_ru`
- `primary_color`
- `bg_color`
- `text_color`
- `sound_default`

Other display fields remain unresolved placeholders:

- `logo`
- `is_paused`
- `is_closed`
- `contrast_default`
- `kiosk_default`

## Why this is a mismatch category, not a false failure

This is not a queue-counter parity failure. It is a contract-shape mismatch:

- legacy route exposes OnlineDay counters
- adapter candidate exposes board/display metadata and queue state separately
- live UI expectations are closer to the adapter metadata shape than to the
  mounted legacy route

## What blocks mounted replacement

Blocking gaps are therefore:

- no legacy parity surface for metadata fields that the live UI actually wants
- unresolved ownership for several metadata fields
- current request contract mismatch between mounted `/board/state` and the live
  frontend call shape

## What does *not* block replacement anymore

The following are no longer the primary blocker:

- strict queue-state parity
- compatibility parity for `is_open` / `start_number`
- existence of an internal adapter seam
