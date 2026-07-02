# Wave 2C Phase 1 Compliance Checklist

Date: 2026-03-07
Mode: analysis-first, execution-enabled
Normative source: `docs/ONLINE_QUEUE_SYSTEM_IMPLEMENTATION.md`

## Extracted Principles That Must Remain Behavior-Compatible

1. `queue_time` defines fairness and must not change for existing queue entries during edits.
2. A patient may have multiple queue entries, one per service or specialist.
3. New services added later must get current edit time and go to the tail for that queue.
4. QR join flow creates queue entries only and does not create visits or appointments.
5. Queue entry `source` semantics are normative: `online`, `desk`, `morning_assignment`.
6. QR availability depends on `opened_at`, `online_start_time`, and `online_end_time`.
7. Queue reads should derive queue data from `OnlineQueueEntry`, not a mixed visit/appointment source.
8. Desk flow and morning assignment semantics are out of scope for Phase 1 mutation work.
9. Legacy queue compatibility exists and must not be rewritten in Phase 1.

## Allowed Phase 1 Work

- compliance docs
- status normalization layer that only adds alias handling
- `QueueDomainService` skeleton with explicit method boundaries
- safe read-only queue slices
- read-only repository boundary introduction
- targeted tests for read-only slices and foundational helpers

## Selected Safe Slices For This Phase

- `W2C-MS-001` (narrowed): queue-position read path helper normalization only
- `W2C-MS-006`: queue snapshot/status read endpoints via a central queue read boundary

These slices are allowed because they do not mutate queue state and do not change numbering,
duplicate policy, or visit linkage semantics.

## Phase 1 Execution Result

- `W2C-MS-001`: completed
- `W2C-MS-006`: completed

Behavior-compatibility checks that remained true after execution:

- queue-position reads still use the same raw visible statuses
- queue snapshot/status reads still use the same reorder-active raw statuses
- no queue mutation handler was migrated
- no numbering, fairness, duplicate, or visit-link rule changed

## Explicitly Disallowed In Phase 1

- `qr_queue` runtime mutation flows
- `registrar_integration.start_queue_visit`
- `doctor_integration` queue mutation orchestration
- `registrar_integration.create_queue_entries_batch`
- `visits.set_status` and `reschedule_*`
- reorder write operations
- legacy queue migration

## Existing Uncertainties That Must Not Be Refactored Through

1. Status vocabulary drift:
   - normative doc: `waiting`, `called`, `completed`, `cancelled`
   - runtime code: also `in_service`, `diagnostics`, `served`, `incomplete`, `no_show`, `canceled`, `rescheduled`, `in_progress`
2. `DailyQueue.specialist_id` semantics:
   - normative doc/checklist implies `users.id` in some places
   - current model uses `doctors.id`
3. Legacy queue coexistence:
   - normative doc says SSOT models are required
   - runtime still uses `OnlineDay` for appointments queue administration

## Stop Conditions For This Phase

Stop immediately if any proposed change would alter:

- numbering
- fairness ordering
- duplicate prevention
- visit to queue linkage
- QR time-window rules
- source semantics
- legacy queue behavior
