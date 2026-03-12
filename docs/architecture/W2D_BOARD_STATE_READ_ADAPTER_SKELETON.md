# W2D BoardStateReadAdapter skeleton

## Added artifact

- [board_state_read_adapter.py](C:/final/backend/app/services/board_state_read_adapter.py)

## What the skeleton now provides

The new internal adapter introduces a stable composition seam with three explicit
sections:

- `display_metadata`
- `queue_state`
- `compatibility`

It currently supports:

- empty skeleton creation via `build_skeleton()`
- narrow internal assembly via `assemble_candidate(...)`
- typed payload output via `BoardStateAdapterPayload`

## What it intentionally does not do yet

- it does not replace mounted [board.py](C:/final/backend/app/api/v1/endpoints/board.py)
- it does not read from real SSOT queue sources yet
- it does not resolve uncertain display fields like `logo`, `is_paused`,
  `is_closed`, `contrast_default`, or `kiosk_default`
- it does not attempt full parity with the current UI contract

Current progress after display-wiring slice:

- confirmed display metadata sources are now wired internally
- announcement input preparation is now wired internally
- queue-state strict fields are now wired internally
- compatibility fields remain intentionally separate

Implementation evidence:

- [board_state_read_adapter.py](C:/final/backend/app/services/board_state_read_adapter.py)
- [test_board_state_display_wiring.py](C:/final/backend/tests/unit/test_board_state_display_wiring.py)

## Why this helps

Before this slice, any future board-state replacement would risk mixing:

- display metadata ownership
- queue counter ownership
- OnlineDay compatibility fields

inside the mounted route itself.

The skeleton makes those concerns explicit before any runtime switch.

## What remains unresolved

- ownership for `is_paused` / `is_closed`
- exact announcement flattening/mapping policy for mounted replacement
- compatibility-only handling for `is_open` / `start_number` in any later
  mounted replacement
- decision on whether future mounted `board_state` should still expose counters

## Future mounted replacement would still need

- adapter data-source wiring
- parity/comparison evidence
- explicit decision on compatibility fields
- bounded route switch in a later slice
