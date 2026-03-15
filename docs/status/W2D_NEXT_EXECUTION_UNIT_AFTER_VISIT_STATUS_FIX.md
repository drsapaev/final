## Next Execution Unit After Visit Status Drift Fix

Date: 2026-03-11
Mode: one-drift-at-a-time, evidence-based

## Chosen next step

`A) fix the next newly discovered pilot drift`

## Why this is the safest next step

- The `Visit.status` blocker is resolved and no longer obscures the marker lane.
- The aggregated Postgres marker lane now fails on one clearly bounded next
  issue in the same confirmation family:
  naive-vs-aware datetime comparison during token-expiry validation.
- This keeps the pilot disciplined and preserves the value of the shared marker
  layer as a trustworthy detector of real remaining drift.

## Why other options are not chosen yet

- `B) proceed to dedicated CI job wiring for postgres_pilot` is premature
  because the aggregated Postgres marker lane is not fully green yet.
- `C) pause and consolidate pilot findings` would interrupt a clean,
  high-signal progression while one localized blocker remains.
- `D) broader status-contract review now justified` is not the right next move
  because the status-length issue is already fixed and the new blocker is a
  datetime-comparison issue instead.

## Exact next slice

A narrow confirmation-family drift-fix pass for:

- `confirmation_expires_at` aware datetime readback vs naive
  `datetime.utcnow()` comparison inside the Postgres marker lane

Why this next:

- it is the only blocker left in the aggregated Postgres marker lane
- it is narrower than CI wiring or broad datetime normalization
- it keeps the one-drift-at-a-time pilot discipline intact
