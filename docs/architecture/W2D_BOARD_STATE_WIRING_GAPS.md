# W2D board_state wiring gaps

## Summary

The adapter skeleton exists, but mounted replacement is still blocked by
metadata ownership and contract mismatch. The blocker is no longer queue
counters; it is the lack of stable, proven owners for several UI-critical board
fields.

## Gap categories

### 1. Missing metadata owners

Fields with no confirmed backend owner:

- `is_paused`
- `is_closed`
- `contrast_default`
- `kiosk_default`

Impact:

- blocks full board-state replacement
- blocks parity claims for the live UI payload

Narrow fix possible:

- only after product/owner clarification or explicit new config ownership

### 2. Logo ownership gap

There is evidence of clinic logo storage/upload:

- [admin_clinic.py](C:/final/backend/app/api/v1/endpoints/admin_clinic.py)
- [admin_clinic_api_service.py](C:/final/backend/app/services/admin_clinic_api_service.py)

But there is no confirmed board-state read owner that maps this into a stable
`logo` field for the live UI.

Impact:

- blocks confident wiring of `logo` into the future adapter

### 3. Announcement shape mismatch

Current likely source:

- `DisplayAnnouncement` rows from [display_config.py](C:/final/backend/app/models/display_config.py)

Current UI expectation:

- flat fields like `announcement`, `announcement_ru`, `announcement_uz`,
  `announcement_en`

Gap:

- a selection + flattening policy is still missing

### 4. Mounted request-contract mismatch

Current mounted [board.py](C:/final/backend/app/api/v1/endpoints/board.py)
requires:

- `department`
- `date`

Current live UI call from
[DisplayBoardUnified.jsx](C:/final/frontend/src/pages/DisplayBoardUnified.jsx)
does not send them.

Impact:

- current route is not usable as-is for the live metadata consumer
- replacement must be staged behind internal adapter prep first

### 5. Mixed concern mismatch

`board_state` currently mixes two different concerns:

- queue/read counters
- display metadata / display config

The adapter skeleton separates them, but production still uses the legacy
counter route.

Impact:

- full replacement remains larger than a single field swap

### 6. Compatibility-only carryover

These fields remain intentionally legacy-backed for now:

- `is_open`
- `start_number`

Impact:

- does not block partial metadata wiring
- does block full OnlineDay retirement for board-state

## What is *not* the main blocker anymore

The following are not the primary blocker for the next slice:

- strict queue counter parity for `last_ticket`, `waiting`, `serving`, `done`
- existence of an internal adapter seam

Those pieces are already in place or sufficiently prepared:

- [board_state_read_adapter.py](C:/final/backend/app/services/board_state_read_adapter.py)
- [W2D_QUEUES_STATS_REPLACEMENT.md](C:/final/docs/architecture/W2D_QUEUES_STATS_REPLACEMENT.md)

## Practical conclusion

The smallest safe next code step is not mounted replacement and not queue-state
wiring. It is metadata-source wiring for fields with already confirmed owners:

- `brand`
- `primary_color`
- `bg_color`
- `text_color`
- `sound_default`

This creates real adapter inputs without forcing unresolved product decisions
for pause/closed state, logo ownership, or announcement flattening.
