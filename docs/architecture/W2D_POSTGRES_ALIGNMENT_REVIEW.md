## Post-W2C Postgres Alignment Review

Date: 2026-03-11
Mode: docs-only checkpoint

## Scope

This review consolidates the completed dual-lane SQLite/Postgres pilot work for
queue-sensitive families.

It answers:

- what the pilot already covered
- what kinds of drift were discovered
- what was *not* discovered
- whether full immediate Postgres migration is justified
- what the safest next engineering step is

## Families covered

| family | SQLite | Postgres | drift |
| --- | --- | --- | --- |
| allocator characterization / concurrency | pass | pass | real schema drift fixed; harness drift fixed |
| open_day / close_day characterization | pass | pass | none |
| queues.stats parity harness | pass | pass | none |
| board_state parity harness | pass | pass | none |
| force_majeure allocator characterization | pass | pass | none |
| confirmation split-flow concurrency | pass | pass | none |
| registrar batch allocator concurrency | pass | pass | none |
| qr_queue direct-SQL concurrency | pass | pass | none |
| qr_queue direct-SQL characterization | pass | pass | schema drift fixed; expectation drift fixed |

## Drifts found during the pilot

### Real schema / ownership drift

- `doctor_treatment_templates.doctor_id` ownership/type mismatch
- `queue_entries.source` length too short for `force_majeure_transfer`
- `DailyQueue.specialist_id` ownership drift between user-oriented and doctor-oriented identities
- `Service.service_code` length too short for legitimate current values

### Harness / session drift

- Postgres pilot temp-schema routing on pooled connections
- `session.refresh(user)` failure in the allocator concurrency family due to
  session-lifecycle/schema-routing behavior in the pilot lane

### Expectation drift

- `queue_time` round-trip mismatch in QR characterization:
  SQLite returned naive `datetime`, Postgres returned aware `datetime` for the
  same `DateTime(timezone=True)` column semantics

## What the pilot did **not** find

Across the covered families, the pilot did **not** reveal meaningful DB-lane
drift in:

- allocator behavior
- queue numbering semantics after the earlier schema fixes
- duplicate/concurrency behavior in the bounded confirmation/registrar/QR
  families
- open/close operational characterization semantics
- queues.stats parity behavior
- board_state parity behavior
- force_majeure allocator characterization behavior
- QR direct-SQL concurrency behavior

It also did **not** justify a broad fixture rewrite to get useful Postgres
signal.

## Strategic conclusion

The dual-lane pilot strategy is now strongly validated.

SQLite remains an acceptable default test baseline **provided that** a bounded
Postgres pilot lane is retained for queue-sensitive families.

This means:

- full immediate migration of the entire test stack to Postgres is **not**
  required at this stage
- the pilot has already covered a broad enough queue/legacy surface to make the
  result trustworthy
- the highest-value next move is to operationalize the pilot as a lightweight
  regression guard, not to keep expanding it indefinitely

## Decision

Recommended posture:

- **Freeze the pilot as a long-term regression guard**
- keep SQLite as the default fast lane
- keep Postgres as a bounded validation lane for sensitive families

This is the best balance of:

- confidence
- cost
- blast radius
- maintenance burden

## Why not broad migration now

Broad immediate Postgres migration is not chosen because:

- the pilot already achieved its main goal
- current evidence does not show systemic hidden drift across the covered
  queue-sensitive areas
- broad fixture churn would now cost more than the likely confidence gain

## Operational outcome

The original operationalization path has now been completed in two bounded
steps:

1. a shared `postgres_pilot` marker was introduced for validated families
2. that marker was wired into a dedicated CI guardrail job

This means the pilot is no longer just a local/manual process. It is now a
repeatable regression guard in CI.

## Recommended next engineering move

With the CI guardrail in place, the safest next move is no longer further pilot
expansion by default.

The project can now return to the broader post-W2C legacy/deprecation tails,
because the bounded Postgres-sensitive queue families already have an automated
guardrail.

Pilot expansion remains available later, but it is no longer the highest-value
default track.
