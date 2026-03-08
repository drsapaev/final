# Wave 2C Registrar Batch Duplicate Contract

Date: 2026-03-08
Mode: analysis-first, docs-only

## Purpose

This document defines the target duplicate contract for the registrar
batch-only allocator subfamily.

It is intentionally narrower than the global queue duplicate contract because
this flow always receives a concrete `patient_id` and operates on a
specialist-day claim.

## Canonical Identity

Registrar batch-only requests must use:

- `patient_id`

The request schema already requires `patient_id`, so contact-based fallback
identity is not part of this contract.

## Claim Key

The batch-only duplicate key is:

`patient_id + specialist_user_id + queue_day`

Where:

- `specialist_user_id` is the resolved `users.id`
- `queue_day` is today's `DailyQueue.day`

## Active Statuses Used In Duplicate Gate

The batch-only duplicate gate should treat these statuses as active:

- `waiting`
- `called`
- `in_service`
- `diagnostics`

## Duplicate Behavior For Same Specialist / Same Day

If an active row already exists for the same:

- `patient_id`
- `specialist_user_id`
- `queue_day`

then registrar batch-only flow should:

- reuse the existing row
- not create a new queue row
- not allocate a new ticket number
- not overwrite the existing `queue_time`
- not rewrite the existing `source`

## Same Specialist With Multiple Services

Registrar batch-only flow should still reuse one specialist-day claim even if
the request contains:

- multiple services for the same specialist
- mixed consultation/diagnostic services for the same specialist
- new services added later in the same day for that specialist

This preserves the local batch contract that claim ownership is specialist-day
scoped, not service-row scoped.

## Allowed Exceptions

Allowed:

- multiple active rows across different specialists on the same day
- a new row for the same patient on the same day when the specialist is
  different

Not allowed by this contract:

- a second active row for the same patient and same specialist/day
- source-based bypass of duplicate prevention
- creating a second row because the existing row is in `diagnostics`

## Override Rules

There is no approved override in the current registrar batch API.

That means:

- `desk` is not an override
- `online` is not an override
- `morning_assignment` is not an override

Any future override would require an explicit contract addition and audit
reason, not an implicit branch in this endpoint.

## Compatibility Note

Current runtime still uses only:

- `waiting`
- `called`

for duplicate reuse. This document defines the target contract, not the current
implementation.
