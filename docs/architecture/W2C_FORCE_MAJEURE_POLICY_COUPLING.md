# Wave 2C Force Majeure Policy Coupling

Date: 2026-03-09
Mode: characterization-first

## Numbering Contract

- Strong coupling.
- `transfer_entries_to_tomorrow()` allocates numbers through its own
  `_get_next_queue_number()` helper.
- Allocation is queue-local for tomorrow's queue and ignores only `cancelled`
  rows.
- This is not yet routed through `QueueDomainService.allocate_ticket()`.

## Duplicate Policy

- Strong coupling.
- Transfer has no canonical duplicate gate against tomorrow's active rows.
- Characterization shows same patient can end up with two active tomorrow rows:
  the existing row plus the new `force_majeure_transfer` row.

## Active-Entry Contract

- Coupled and currently divergent.
- `get_pending_entries()` docstring claims `waiting`, `called`, `in_service`,
  `diagnostics`, but runtime filter currently uses only `waiting` and `called`.
- That means the family owns a narrower active set than the target queue
  contract.

## Fairness / Order

- Strong coupling.
- Transfer explicitly overrides ordinary fairness by:
  - assigning `priority=2`
  - resetting `queue_time` to a new timestamp
- This is intentional policy override, not normal queue preservation.

## Queue-Time Immutability

- Strong coupling.
- Transfer does not preserve the old `queue_time`.
- Cancellation terminates the old row instead of preserving it.

## Source Ownership

- Strong coupling.
- New transfer rows explicitly set `source="force_majeure_transfer"`.
- This is exceptional-source semantics, not ordinary carry-through.

## Visit Linkage

- Coupled.
- Transfer copies `visit_id` onto the new row.
- Cancel flow uses `visit_id` to find payment/refund consequences.

## Transfer Semantics

- Core defining behavior of this family.
- The family is an exceptional operational transfer domain, not a normal
  allocator caller.
- Migration must preserve explicit override semantics or clarify them first.
