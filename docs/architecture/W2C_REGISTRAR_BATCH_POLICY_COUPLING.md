# Wave 2C Registrar Batch Policy Coupling

Date: 2026-03-07
Mode: characterization-first, docs-only

## Summary

Registrar batch-only flow is narrower than the broader registrar family, but it
is still coupled to multiple queue policies.

It is **not** payment-heavy inside the allocator path, but it is not a trivial
"swap the caller to the boundary" slice either.

## Numbering Coupling

Current runtime numbering path:

1. mounted endpoint decides whether to reuse or create
2. create path calls `queue_service.create_queue_entry(auto_number=True)`
3. allocator internally calls `get_next_queue_number(...)`

Implications:

- numbering algorithm is still legacy
- caller does not own numbering directly
- caller does own the decision of whether numbering should run at all

## Duplicate Policy Coupling

Mounted runtime duplicate gate is:

- `patient_id`
- queue/day scoped through `DailyQueue`
- statuses only `waiting` / `called`

Implications:

- current batch-only flow is narrower than the canonical duplicate contract
- it ignores contact-based fallback identity
- it ignores `diagnostics` and `in_service` as duplicate-blocking states

## Active Entry Semantics Coupling

This flow is explicitly coupled to a non-canonical active set.

Characterized runtime:

- existing `waiting` row => reused
- existing `called` row => reused
- existing `diagnostics` row => does **not** block new allocation

This is the strongest current contract conflict.

## Service Cart Semantics Coupling

Batch-only grouping key is:

- resolved `specialist_id`

Not:

- `queue_tag`
- `service_id`
- canonical queue claim

Characterized runtime:

- two services for the same specialist but different `queue_tag` values produce
  one queue row

This means allocator behavior is coupled to cart grouping policy, not only to
queue allocation policy.

## Source Ownership Coupling

The batch endpoint preserves request `source` on new rows.

Observed accepted runtime values:

- `online`
- `desk`
- `morning_assignment`

Implications:

- source semantics are upstream-controlled
- repeated duplicate reuse does not rewrite source on existing row
- boundary migration must preserve this source pass-through behavior unless the
  registrar contract is explicitly narrowed later

## Fairness / Order Coupling

Current fairness behavior:

- new rows get one shared `current_time` captured for the batch request
- reused rows keep their old `queue_time`
- numbering remains monotonic through legacy allocator

Observed serialization detail:

- response `queue_time` includes `+05:00`
- persisted SQLite test rows surface as naive local datetime

This is an output-format/runtime-storage drift, not a proven fairness bug.

## Session Identity Coupling

`queue_service.create_queue_entry()` assigns `session_id` using:

- `patient_id`
- `queue_id`
- `queue_day`

Implications:

- batch-only creation also mutates queue session identity state
- repeated batch submission that reuses an existing row keeps a single
  session-bound queue claim

## Visit Lifecycle Coupling

Within the narrow batch-only scope, direct visit lifecycle coupling is low.

This flow:

- does not create visits
- does not update visit status
- does not attach queue rows to visit IDs

Upstream registrar edit flows may be visit-related, but the allocator subfamily
itself is queue-row oriented.

## Billing / Payment Coupling

Direct billing/payment coupling inside the batch-only allocator path is low.

Observed runtime:

- no invoice creation
- no payment state writes
- no cashier/provider side effects

This removes one major blocker, but does not remove the duplicate/active-status
contract blocker.

## Architectural Drift

Mounted runtime still keeps batch allocator orchestration in router-level ORM
logic, while a cleaner seam already exists in:

- `QueueBatchService`
- `QueueBatchRepository`
- unmounted `registrar_integration_api_service.py`

This is migration-relevant drift, not immediate proof that behavior can be
changed safely.
