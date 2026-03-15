# W2D next execution unit after board_state skeleton

Decision: `A) board_state data-source wiring prep`

## Why this is the safest next step

- the adapter seam now exists, so the next bounded step is to map real owners
  into that seam
- the main unresolved risk is no longer structural mixing; it is missing evidence
  for real metadata and queue-state sources
- wiring prep can stay internal and still avoid any mounted replacement

## Why not the larger options yet

- Not `board_state parity/comparison harness`:
  - a parity harness would be weaker before the adapter has real candidate inputs
  - right now the skeleton is still mostly shape-only
- Not `human review needed`:
  - the next bounded technical step is clear enough
- Not `stop board_state track for now`:
  - this surface still blocks future OnlineDay read retirement work
