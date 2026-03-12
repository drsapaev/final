## Wave 2D Visit Status Drift Fix

Date: 2026-03-11
Mode: one-drift-at-a-time, evidence-based

## Exact mismatch fixed

The aggregated Postgres `postgres_pilot` lane failed in the confirmation family
because `Visit.status` was too short for a legitimate current runtime value.

Before this slice:

- `Visit.status` was declared as `String(16)`
- current runtime/test code already used `pending_confirmation`
- Postgres rejected that value under strict `VARCHAR(16)` enforcement
- SQLite accepted it, masking the mismatch

Applied fix:

- widened `Visit.status` from `String(16)` to `String(20)` in
  `backend/app/models/visit.py`

## Intended ownership

This is still the same bounded visit-status field. The fix does not redefine
the status system; it only aligns the schema with legitimate current runtime
usage already present in app code and tests.

Confirmed current status vocabulary includes:

- `open`
- `closed`
- `canceled`
- `cancelled`
- `paid`
- `in_visit`
- `in progress`
- `completed`
- `done`
- `pending_confirmation`
- `confirmed`
- `scheduled`
- `expired`

The longest confirmed current value is `pending_confirmation` with length `20`.

## Why `20` is the narrowest honest fix

- it fits the longest currently confirmed runtime value
- it does not introduce a broad status-contract redesign
- it preserves existing integrity semantics
- it stays aligned with one-drift-at-a-time pilot discipline

## Validation added

Added:

- `backend/tests/unit/test_visit_status_schema.py`

This guard proves:

- `Visit.status` is now `String(20)`
- the currently confirmed runtime values fit within the declared bound

## Postgres pilot impact

This fix removed the confirmation-family schema blocker in the aggregated
Postgres marker lane.

After the fix:

- the SQLite marker lane remains green
- the Postgres marker lane progresses beyond the old length mismatch
- the next honest blocker is now a datetime comparison issue in the same
  confirmation family:
  naive `datetime.utcnow()` vs aware `confirmation_expires_at`

That means the `Visit.status` mismatch is resolved cleanly, and the pilot can
continue surfacing one bounded issue at a time.

## Out of scope

- broad visit-status normalization
- enum/system-wide status refactor
- confirmation flow redesign
- broad datetime normalization
- CI wiring for `postgres_pilot`
