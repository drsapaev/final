# W2D queues.stats replacement readiness

Verdict: `READY_WITH_COMPATIBILITY_FALLBACK`

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

## Why not fully READY_FOR_NARROW_REPLACEMENT without caveat
Two legacy compatibility fields still lack a clean SSOT owner:
- `is_open`
- `start_number`

These fields should stay on legacy fallback or explicit compatibility handling in the first replacement slice.

## What this means
A narrow replacement for `queues.stats` is now reasonable if:
- strict fields come from the SSOT read-model
- compatibility fields remain legacy-backed or explicitly deferred
- mounted contract shape stays unchanged
