# W2D queues.stats replacement status

Status: `APPLIED_WITH_COMPATIBILITY_FALLBACK`

## Implemented
- [queues.py](C:/final/backend/app/api/v1/endpoints/queues.py) `stats()` now builds its response through [queue_stats_parity_harness.py](C:/final/backend/app/services/queue_stats_parity_harness.py)
- strict counter fields use SSOT-backed computation when queue mapping resolves:
  - `last_ticket`
  - `waiting`
  - `serving`
  - `done`
- compatibility fields still come from the OnlineDay legacy island:
  - `is_open`
  - `start_number`

## Safety guard retained
If the requested department/day does not resolve to SSOT queues, the endpoint preserves legacy strict counters instead of returning a zeroed SSOT projection.

## Current source ownership
- SSOT-backed when mapping resolves:
  - `last_ticket`
  - `waiting`
  - `serving`
  - `done`
- Legacy-backed compatibility fields:
  - `is_open`
  - `start_number`
- Legacy strict fallback for unmapped legacy departments:
  - `last_ticket`
  - `waiting`
  - `serving`
  - `done`

## Tests
- [test_queues_stats_parity_harness.py](C:/final/backend/tests/characterization/test_queues_stats_parity_harness.py)
- [test_queues_stats_replacement.py](C:/final/backend/tests/unit/test_queues_stats_replacement.py)

## Remaining work
- board-state replacement prep
- full cutover decision for unmapped legacy department keys
- eventual retirement of OnlineDay compatibility fields after adjacent read surfaces are replaced
