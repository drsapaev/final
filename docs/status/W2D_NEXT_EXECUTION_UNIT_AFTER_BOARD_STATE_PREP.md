# W2D next execution unit after board_state prep

Decision: `B) board_state read-adapter skeleton only`

## Why this is the safest next step

- [board.py](C:/final/backend/app/api/v1/endpoints/board.py) `board_state()` is not just a legacy counter route; it is a contract-drift surface.
- The current UI expects board/display metadata, while the mounted runtime still returns only OnlineDay counters.
- There is already a plausible future owner direction in the display-config domain, but not enough proven parity to replace the mounted route safely.
- A read-adapter skeleton can isolate ownership and composition without changing runtime behavior.

## Why not the larger options yet

- Not `board_state counters only`:
  - current UI does not rely on counters from `/board/state`
  - counters alone would not solve the real consumer gap
- Not `board_state partial replacement with compatibility fallback`:
  - there is no proven backend owner yet for `is_paused`, `is_closed`, and several board defaults
  - the route request contract is still mismatched with the current consumer
- Not `human review needed`:
  - the next bounded step is clear enough: create the adapter seam first, then characterize parity against it
