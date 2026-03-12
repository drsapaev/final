# Wave 2D Next Execution Unit After OnlineDay Dead Cleanup

Date: 2026-03-09
Mode: cleanup-first, docs-only

## Decision

`A) support-only OnlineDay mirror cleanup slice`

## Why this is the best next step

- The truly dead endpoint modules are already removed.
- The next-lowest-risk bucket is the support-only mirror layer:
  - `online_queue_api_service.py`
  - `appointments_api_service.py`
  - `board_api_service.py`
  - `queues_api_service.py`
- Live mounted OnlineDay endpoints remain explicitly out of scope.
- `backend/app/crud/queue.py` now requires its own later review, so it should
  not block the support-only mirror cleanup path.

## Why the other options were not chosen

### `B) live mounted endpoint replacement prep`

Still needed later, but not the narrowest safe next step while support-only
mirrors remain.

### `C) human review needed`

Not required for the next cleanup slice. The support-only mirror bucket is
already identified and narrower than live endpoint work.

### `D) stop OnlineDay cleanup track for now`

Not justified. Cleanup can still progress safely on non-mounted surfaces.
