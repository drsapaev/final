# W2D next execution unit after queues.stats replacement

Decision: `A) board_state replacement prep`

## Why this is the safest next step
- [queues.py](C:/final/backend/app/api/v1/endpoints/queues.py) `stats()` is now partially decoupled from the OnlineDay island for strict consumer-visible counters.
- The next adjacent live OnlineDay read surface is [board.py](C:/final/backend/app/api/v1/endpoints/board.py) `board_state()`.
- Preparing `board_state` next reduces uncertainty around the remaining legacy read-model before attempting any full cutover for `queues.stats`.

## Why not the larger options yet
- Not `queues.stats` full cutover:
  - `is_open` and `start_number` still have no clean SSOT owner.
  - legacy department/day requests may still require compatibility handling.
- Not `next_ticket` replacement prep:
  - it is a write/state-changing surface and therefore higher risk than the remaining read-model prep.
- Not `human review needed`:
  - the next safe step is already clear and bounded.
