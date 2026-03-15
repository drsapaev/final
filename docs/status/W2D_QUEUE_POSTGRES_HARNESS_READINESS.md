## Wave 2D Queue Postgres Harness Readiness

Date: 2026-03-11
Mode: pilot-first, evidence-based

Verdict: `PILOT_SUCCESS_READY_FOR_NEXT_FAMILY`

## Why

- The default SQLite lane remains green.
- The targeted Postgres pilot lane is green for several bounded families and
  continues to give useful signal.
- Earlier real schema drifts were fixed honestly one at a time:
  `doctor_treatment_templates.doctor_id`,
  `queue_entries.source`,
  `DailyQueue.specialist_id`.
- The earlier allocator family blocker turned out to be a pilot
  harness/session-lifecycle issue, not another application drift.
- The newly extended QR characterization family first surfaced a bounded schema
  drift in `Service.service_code` length enforcement under Postgres, and that
  drift was fixed narrowly.
- After that, the same family exposed a `queue_time` round-trip mismatch that
  was resolved as test expectation drift rather than a new application defect.
- The QR characterization family is green in both SQLite and Postgres lanes.
- After operationalizing the pilot with a shared `postgres_pilot` marker, the
  aggregated Postgres lane surfaced a new bounded drift in the confirmation
  family.
- That confirmation-family schema drift in `Visit.status` has been fixed
  narrowly.
- The follow-up confirmation-family datetime-awareness drift has also been
  fixed narrowly.
- The aggregated marker lane is now green in both SQLite and Postgres backends.

## What this means

- The dual-validation pilot strategy remains validated strongly enough to
  continue.
- We still do not need a broad fixture rewrite.
- The safest next move is to fix the newly surfaced bounded drift, then
  continue the same pilot approach.

## Current state

- SQLite pilot family: `7 passed`
- Postgres pilot family: `7 passed`
- SQLite open/close pilot family: `3 passed`
- Postgres open/close pilot family: `3 passed`
- SQLite queues.stats pilot family: `3 passed`
- Postgres queues.stats pilot family: `3 passed`
- SQLite board_state pilot family: `3 passed`
- Postgres board_state pilot family: `3 passed`
- SQLite force_majeure pilot family: `2 passed`
- Postgres force_majeure pilot family: `2 passed`
- SQLite confirmation pilot family: `2 passed`
- Postgres confirmation pilot family: `2 passed`
- SQLite registrar-batch pilot family: `2 passed`
- Postgres registrar-batch pilot family: `2 passed`
- SQLite QR pilot family: `2 passed`
- Postgres QR pilot family: `2 passed`
- SQLite QR characterization pilot family: `4 passed`
- Postgres QR characterization pilot family: `4 passed`
- SQLite marker lane: `28 passed, 761 deselected`
- narrow visit-status schema test: `1 passed`
- narrow confirmation datetime test: `2 passed`
- Postgres marker lane: `28 passed, 764 deselected`
- SQLite marker lane: `28 passed, 764 deselected`
- OpenAPI verification: `10 passed`

## Readiness implication

Continue the pilot approach, but fix the newly surfaced bounded drift first.

Do not broaden into full test-stack migration yet.

The latest follow-up still confirms that the strategy works as designed:

- first it exposed real Postgres-enforced schema mismatches
- then it exposed narrower harness/expectation mismatches
- now, when grouped behind a reusable marker layer, the pilot lane is green in
  both DB backends after a series of bounded, honest fixes
- this validates the pilot strongly enough to promote the marker lane into a
  dedicated CI guardrail without requiring broad fixture migration first

The strategy is now validated on:

- allocator characterization/concurrency
- legacy open/close operational characterization
- queues.stats parity harness characterization
- board_state parity harness characterization
- force_majeure allocator characterization
- confirmation split-flow concurrency characterization
- registrar batch allocator concurrency characterization
- QR direct-SQL concurrency characterization
- QR direct-SQL characterization

## Readiness implication

The dual-lane pilot strategy is now validated strongly enough to move from
bounded drift cleanup into dedicated CI wiring for `postgres_pilot`.
