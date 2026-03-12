## Next Execution Unit After Queue Postgres Harness

Date: 2026-03-10
Mode: pilot-first, evidence-based

## Chosen next step

`C) fix a specific discovered DB-drift issue`

## Exact first slice

Narrow Postgres schema-bootstrap fix for the discovered metadata mismatch:

- `doctor_treatment_templates.doctor_id`
- `users.id`

## Why this is the safest next step

- The harness itself already proved its value.
- The default SQLite suite remains stable.
- The Postgres lane is currently blocked by one concrete metadata incompatibility
  rather than by a broad fixture problem.

## Why broader steps are not chosen yet

- Extending the pilot to another queue family would fail at the same bootstrap
  point.
- Broad fixture-layer prep would be premature because the next blocker is not
  fixture design; it is schema parity.
- Holding for review would add less value than fixing the now-proven blocker.
