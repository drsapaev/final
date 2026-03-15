# W2D queues.stats replacement readiness

Verdict: `APPLIED_WITH_COMPATIBILITY_FALLBACK`

## Evidence
- legacy-vs-SSOT comparison harness exists:
  - [queue_stats_parity_harness.py](C:/final/backend/app/services/queue_stats_parity_harness.py)
- representative characterization coverage exists:
  - [test_queues_stats_parity_harness.py](C:/final/backend/tests/characterization/test_queues_stats_parity_harness.py)
- strict parity achieved for:
  - `last_ticket`
- `waiting`
- `serving`
- `done`

## What is already replaced
- mounted [queues.py](C:/final/backend/app/api/v1/endpoints/queues.py) `stats()` now serves strict counters from SSOT-backed logic when queue mapping resolves
- response contract shape is unchanged
- validation behavior is unchanged

## What remains before full cutover
Two legacy compatibility fields still lack a clean SSOT owner:
- `is_open`
- `start_number`

There is also a deliberate legacy fallback for strict counters when a legacy department/day request does not resolve to SSOT queues.

## What this means
The narrow replacement slice is complete, but full OnlineDay retirement is not.
Before a full cutover, we still need:
- replacement prep for adjacent `board_state` read surfaces
- an explicit decision on how unmapped legacy department keys should behave
- a replacement or retirement path for `is_open` and `start_number`
