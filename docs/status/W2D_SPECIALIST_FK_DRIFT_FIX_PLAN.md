## W2D Specialist FK Drift Fix Plan

## Exact current mismatch

- [online_queue.py](C:/final/backend/app/models/online_queue.py) declares
  `DailyQueue.specialist_id` as `Integer, ForeignKey("doctors.id")`.
- The mounted registrar batch path in
  [registrar_integration.py](C:/final/backend/app/api/v1/endpoints/registrar_integration.py)
  still normalizes some inputs to `user_id` and then creates `DailyQueue` rows
  with that value.
- SQLite tolerated this drift; the Postgres pilot does not.

## Current model/runtime evidence

- `Doctor.id` is the primary key for [Doctor](C:/final/backend/app/models/clinic.py).
- `Doctor.user_id` links a doctor record back to [User](C:/final/backend/app/models/user.py).
- [queue_service.py](C:/final/backend/app/services/queue_service.py) already
  treats `DailyQueue.specialist_id` as canonical `doctor.id` and accepts either
  `doctor.id` or `user.id` only as an input convenience.
- The mounted registrar batch path drifted away from that rule and wrote
  `user.id`-shaped values into `DailyQueue.specialist_id`.

## Intended target relation

- `DailyQueue.specialist_id -> doctors.id`
- External request payloads may still arrive as either `doctor.id` or `user.id`
  during transition, but the stored queue owner must be canonicalized to
  `doctor.id`.

## Chosen narrow fix

- Keep the FK target as `doctors.id`.
- Fix the mounted registrar batch path so it canonicalizes incoming
  `specialist_id` to `doctor.id` before querying/creating `DailyQueue`.
- Preserve the existing external request/response surface as much as possible.

## Explicitly out of scope

- Postgres `session.refresh(user)` issue
- broad queue identity redesign
- broad refactor of legacy helper layers that still encode user-facing specialist ids
- any queue allocator behavior change beyond this ownership correction
