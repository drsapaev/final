# W2D queues.stats parity results

## Proven parity
Representative characterization cases show strict parity for:
- `last_ticket`
- `waiting`
- `serving`
- `done`

Covered cases:
- empty / low-volume department-day
- non-zero mixed-status department-day
- department/day mapping case where unrelated department queues must be excluded

## Current mismatch categories
- `is_open`
  - legacy source: `OnlineDay.is_open`
  - candidate SSOT harness: no equivalent owner yet
  - category: deferred compatibility field
- `start_number`
  - legacy source: `OnlineDay.start_number`
  - candidate SSOT harness: no department/day SSOT owner yet
  - category: deferred compatibility field

## Why the strict fields can match
- `last_ticket` can be reproduced as max queue number across matched SSOT entries
- `waiting` maps to `status == "waiting"`
- `serving` maps to in-flight care states:
  - `called`
  - `in_service`
  - `diagnostics`
- `done` maps to `status == "served"`

## Department/day mapping assumptions
The candidate harness currently resolves legacy `department + day` to SSOT queues via:
- `QueueProfile.department_key -> queue_tags`
- fallback to `Doctor.department`
- fallback to direct `queue_tag` / `doctor.specialty` match

This is good enough for representative parity evidence, but still a read-model assumption rather than a formally mounted replacement contract.

## Replacement impact
- strict parity fields are the only confirmed live UI requirement for `queues.stats`
- deferred compatibility fields do not currently block the smallest replacement slice
- board/display metadata remains out of scope for this endpoint
