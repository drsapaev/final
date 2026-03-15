# Wave 2C Registrar Batch Behavior Correction

Date: 2026-03-08
Mode: behaviour-correction, small diff
Scope: mounted registrar batch-only flow

## Old Runtime Behavior

Before this slice, mounted registrar batch duplicate gate reused existing rows
only when status was:

- `waiting`
- `called`

That caused two concrete problems:

1. an existing `diagnostics` row did not block a new allocation
2. an existing `in_service` row would also have been ignored by the same gate

Result:

- batch add could create a new `waiting` row for the same
  `patient_id + specialist_user_id + queue_day`
- a new number could be allocated even though the patient already had a live
  specialist-day claim

## Corrected Behavior

Mounted registrar batch duplicate gate now treats these statuses as active:

- `waiting`
- `called`
- `in_service`
- `diagnostics`

That means:

- if exactly one active row exists for the same specialist-day claim, it is
  reused
- no new queue row is created
- no new number is allocated
- existing `queue_time` is preserved
- existing `source` is preserved

## Ambiguity Handling

If more than one active row already exists for the same:

- `patient_id`
- `queue_id`

the mounted batch path now returns explicit `409 Conflict` instead of choosing
one row implicitly or allocating another row.

This is the safe behavior for a specialist-level claim model because ownership
is already inconsistent in that case.

## Why This Matches The Approved Contracts

The correction aligns runtime with:

- [W2C_ACTIVE_ENTRY_CONTRACT.md](C:/final/docs/architecture/W2C_ACTIVE_ENTRY_CONTRACT.md)
- [W2C_DUPLICATE_POLICY_CONTRACT.md](C:/final/docs/architecture/W2C_DUPLICATE_POLICY_CONTRACT.md)
- [W2C_REGISTRAR_BATCH_DUPLICATE_CONTRACT.md](C:/final/docs/architecture/W2C_REGISTRAR_BATCH_DUPLICATE_CONTRACT.md)
- [W2C_REGISTRAR_BATCH_CLAIM_MODEL.md](C:/final/docs/architecture/W2C_REGISTRAR_BATCH_CLAIM_MODEL.md)

Specifically:

- `diagnostics` is now treated as active for this family
- registrar batch-only claim remains specialist-level
- no same-claim duplicate row is created when ownership is clear

## What Did Not Change

- numbering algorithm
- queue-time assignment for newly created rows
- fairness ordering
- source passthrough on create
- broader registrar wizard orchestration
- QR allocator behavior
- `OnlineDay`
- force-majeure paths

## Readiness Impact

This slice removes the main behavior drift that blocked registrar batch-only
boundary migration.

The family is still narrow in scope, but it is now clean enough for the next
step to be caller-path migration rather than more contract clarification.
