# Wave 2C Confirmation Behavior Correction

Date: 2026-03-07
Mode: behaviour-correction, small-diff execution

## Scope

This slice corrected only the confirmation family behavior around same-queue
active-entry reuse.

Included:

- mounted public confirmation flow in
  `backend/app/services/visit_confirmation_service.py`
- mounted registrar confirmation bridge in
  `backend/app/api/v1/endpoints/registrar_wizard.py`

Not included:

- allocator algorithm redesign
- `qr_queue` migration
- `OnlineDay` legacy migration
- broad registrar family migration

## Pre-Correction Runtime Behavior

Before this slice, same-day confirmation behaved like this:

1. resolve queue/day and queue tag
2. call legacy `get_next_queue_number(...)`
3. create a fresh `OnlineQueueEntry(source="confirmation")`

That happened even when an active queue row already existed for the same
patient in the same queue/day.

Observed consequences:

- a second active row could be created in the same queue
- a new historical ticket number could be consumed unnecessarily
- duplicate-policy contract was bypassed inside confirmation

## Corrected Runtime Behavior

The mounted confirmation paths now apply a narrow canonical active-entry gate
before queue creation.

### Canonical active statuses

- `waiting`
- `called`
- `in_service`
- `diagnostics`

### Canonical identity preference

1. `patient_id`
2. normalized phone
3. normalized telegram id

### New decision tree

#### Clear existing active row found

- do not call `create_queue_entry()`
- do not allocate a new ticket number
- reuse the existing row
- preserve `number`
- preserve `queue_time`
- preserve fairness ordering
- link the row to the confirmed visit if `visit_id` was empty
- backfill `patient_id` only if the reused row had no `patient_id`

#### No active row found

- current legacy queue-entry creation path still runs
- numbering algorithm stays unchanged

#### Ambiguous existing rows

If multiple active rows match the canonical identity, or the only matched row is
already linked to another visit/patient in a conflicting way:

- confirmation returns an explicit conflict error
- no new queue row is created

## Why This Matches The Design Better

This correction now matches the clarified design intent:

- multiple rows remain valid across different queue claims
- confirmation no longer creates a second active row in the same queue/day by
  default
- existing queue ownership is reused when it is already clear

## Why This Matches The Domain Contracts Better

### Duplicate-policy contract

Now confirmation no longer silently allocates another queue row when an active
claim already exists in the same queue/day.

### Active-entry contract

The gate now uses the canonical active set instead of the old narrower
`waiting/called` assumption.

### Numbering contract

Number allocation remains:

- monotonic
- queue-local
- day-scoped

But it now runs only when confirmation actually needs a new queue row.

## Remaining Ambiguity Cases

The correction intentionally does not "best-effort" ambiguous situations.

Explicit conflict remains when:

- multiple active rows match the same canonical queue claim
- the matching row is already linked to a different visit
- identity signals point to conflicting active rows

This is intentional and matches the approved fallback contract.

## Later Boundary Migration Readiness

After this correction, the mounted confirmation family is ready for a later
narrow migration through `QueueDomainService.allocate_ticket()`:

- the duplicate-versus-reuse rule is now explicit
- mounted public and registrar confirmation paths share the same corrected
  queue-assignment logic
- allocator algorithm itself remains legacy and unchanged

This slice did not perform that migration. It only removed the contract drift
that previously blocked it.
