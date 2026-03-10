# W2D queues.stats replacement

## Old path
- Mounted endpoint: [queues.py](C:/final/backend/app/api/v1/endpoints/queues.py) `stats()`
- Old source of truth for all fields: `app.services.online_queue.load_stats(...)`

## New path
- Mounted endpoint still stays the same: `GET /api/v1/queues/stats`
- Strict counters now go through [queue_stats_parity_harness.py](C:/final/backend/app/services/queue_stats_parity_harness.py)
- Endpoint builds a mixed snapshot:
  - SSOT-backed strict counters when department/day mapping resolves
  - legacy compatibility fallback for `is_open` and `start_number`
  - safety fallback to legacy strict counters when no SSOT queue mapping resolves

## Strict SSOT-backed fields
- `last_ticket`
- `waiting`
- `serving`
- `done`

## Compatibility legacy fields
- `is_open`
- `start_number`

## Legacy fallback retained on purpose
- If the requested department/day resolves to SSOT queues, strict counters come from the SSOT read-model.
- If the requested department/day does not resolve to SSOT queues, the endpoint preserves legacy strict counters instead of returning a zeroed SSOT snapshot.

This keeps current legacy consumers safe while replacement work for adjacent OnlineDay read surfaces is still pending.

## Why behavior is preserved
- route path is unchanged
- response keys are unchanged
- validation behavior is unchanged
- legacy-compatible fallback is preserved for unmapped legacy department/day requests

## What remains before full cutover
- remove compatibility fallback for `is_open`
- remove compatibility fallback for `start_number`
- decide how unmapped legacy department keys should be handled
- prepare adjacent `board_state` replacement so the remaining OnlineDay read surface is understood before deeper legacy retirement
