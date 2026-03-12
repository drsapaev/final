# W2D Source Length Drift Fix Plan

## Exact mismatch

- Current schema declaration in [online_queue.py](C:/final/backend/app/models/online_queue.py) defines `queue_entries.source` as `String(20)`.
- Current runtime already uses `source="force_majeure_transfer"` in [force_majeure_service.py](C:/final/backend/app/services/force_majeure_service.py).
- `force_majeure_transfer` is 22 characters long, so Postgres rejects inserts for that value during the pilot run.

## Current model/domain evidence

Confirmed queue-entry `source` values used in active code and characterization coverage:

- `online`
- `desk`
- `confirmation`
- `morning_assignment`
- `migration`
- `batch_update`
- `force_majeure_transfer`

Max observed current legitimate value length: `22` (`force_majeure_transfer`).

## Intended target relation / meaning

- `queue_entries.source` is an existing free-form but bounded provenance field for legitimate queue-entry creation paths.
- `force_majeure_transfer` is already part of current runtime behavior, not a speculative future value.

## Chosen narrow fix

- Increase `queue_entries.source` from `String(20)` to `String(24)`.
- This is the smallest bounded fix that fits all currently observed legitimate values with a small safety margin.
- Do **not** turn the field into unbounded text.
- Do **not** introduce an enum or broader source-domain refactor in this slice.

## Explicitly out of scope

- `DailyQueue.specialist_id` FK drift
- Postgres session/refresh issue in the concurrency pilot
- force_majeure redesign
- broader queue source normalization or enum cleanup
