## Wave 2D DailyQueue.specialist_id FK Drift Fix

Date: 2026-03-10
Mode: narrow ownership/schema drift fix

## Exact mismatch fixed

`DailyQueue.specialist_id` is declared as an `INTEGER` foreign key to
`doctors.id`, but some runtime and test paths still treated it like a
user-oriented identifier.

The concrete Postgres pilot blocker was a strict-FK failure inside the queue
allocator pilot family:

- one path supplied a user-oriented specialist identity
- Postgres enforced `DailyQueue.specialist_id -> doctors.id`
- SQLite allowed the suite to continue without exposing that mismatch early

## Intended ownership

Confirmed target ownership:

- `DailyQueue.specialist_id` belongs to `doctors.id`
- `Doctor.user_id` remains an input compatibility identity only
- legacy callers may still pass `users.id`, but queue creation helpers must
  canonicalize that input to `doctor.id` before reading or writing

Evidence:

- `backend/app/models/online_queue.py` defines the FK to `doctors.id`
- `backend/app/models/visit.py` defines `Visit.doctor_id` as FK to `doctors.id`
- `backend/app/services/queue_service.py` already canonicalized legacy input to
  `doctor.id`
- registrar batch and confirmation-family test flows proved that some callers
  still arrived with user-oriented ids

## Narrow fix applied

The slice corrected ownership drift in three places:

1. mounted registrar batch flow now resolves the request specialist to the
   canonical `doctor.id` before queue lookup/creation
2. legacy CRUD helper `get_or_create_daily_queue(...)` now accepts both
   `doctor.id` and `doctor.user_id`, but deterministically stores/queries only
   `doctor.id`
3. queue-sensitive tests/fixtures now reuse the canonical doctor owner instead
   of creating ambiguous user-vs-doctor drift

## Why this is the narrowest honest fix

- it does not redesign queue identities
- it does not weaken FK integrity
- it does not change the public meaning of queue allocation
- it only aligns persisted ownership with the model contract that already
  exists in code

## What stayed out of scope

- the separate Postgres-lane `session.refresh(user)` failure
- broad queue identity redesign
- full fixture-layer rewrite
- any runtime changes outside the `DailyQueue.specialist_id` ownership path
