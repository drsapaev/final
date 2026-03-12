## Wave 2D Visit Status Drift Fix Plan

Date: 2026-03-11
Mode: one-drift-at-a-time, evidence-based

## Exact mismatch

The Postgres `postgres_pilot` lane surfaced a strict length mismatch in the
confirmation family:

- `Visit.status` is currently declared as `String(16)`
- current runtime/test code already uses `status="pending_confirmation"`
- Postgres rejects that value because it enforces `VARCHAR(16)` strictly
- SQLite accepted it, which hid the mismatch

## Current schema declaration

- `backend/app/models/visit.py`
  - `status: mapped_column(String(16), nullable=False, default="open")`

## Confirmed legitimate status values

Confirmed in current app/tests/runtime code:

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

## Max observed / current expected length

The longest currently confirmed legitimate value is:

- `pending_confirmation` -> length `20`

This makes the mismatch a bounded length issue first, not a full status-system
design issue.

## Chosen fix

Widen only the model-level `Visit.status` column from `String(16)` to
`String(20)`.

Add a narrow schema guard test proving that:

- the column length now matches the longest currently confirmed runtime value
- current shorter status values still fit

## Why this is the narrowest honest fix

- It fixes the exact Postgres-enforced mismatch and nothing broader.
- It follows current runtime/domain usage instead of inventing a new vocabulary.
- It does not remove integrity, indexing, or defaults.
- It avoids pulling a broader status-normalization track into this slice.

## Explicitly out of scope

- broad visit-status normalization
- enum refactor across all visit flows
- queue/confirmation behavior changes
- unrelated Postgres pilot drift fixes
- CI wiring for `postgres_pilot`
