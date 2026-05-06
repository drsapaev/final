# Wave 2C Confirmation Boundary Migration

Date: 2026-03-07
Mode: behaviour-preserving migration

## Goal

Move the mounted confirmation family onto the queue allocation compatibility
boundary without changing confirmation behavior after the Phase 2.4 correction.

## Old Caller Path

Mounted confirmation family previously depended on legacy allocation directly:

1. `VisitConfirmationService._assign_queue_numbers_on_confirmation(...)`
2. `queue_service.get_next_queue_number(...)`
3. `queue_service.create_queue_entry(...)`

That direct dependency was narrow, but it bypassed the new queue-domain
boundary.

## New Caller Path

Mounted confirmation family now uses:

1. `VisitConfirmationService._assign_queue_numbers_on_confirmation(...)`
2. `QueueContextFacade.allocate_ticket(...)`
3. `QueueDomainServiceContractAdapter.allocate_ticket(...)`
4. `QueueDomainService.allocate_ticket(...)`
5. legacy `queue_service.create_queue_entry(...)`

## Why The Facade Is Used

`visit_confirmation_service` is a cross-context caller relative to the queue
domain. Directly importing `QueueDomainService` would violate the project
context-boundary rule enforced by `tests/architecture/test_context_boundaries.py`.

The mounted confirmation family therefore uses:

- `QueueContextFacade`
- `QueueDomainServiceContractAdapter`

This keeps the migration aligned with the target architecture:

- caller depends on a queue contract seam
- queue domain boundary remains the owner of the public allocator method
- legacy allocator internals remain unchanged

## Behavior Preservation Notes

This migration does **not** change:

- confirmation reuse-existing-entry logic
- ambiguity conflict handling
- numbering algorithm
- `queue_time` assignment semantics
- fairness ordering
- response schema

## What Still Remains Outside The Boundary

- standalone `get_next_queue_number(...)` helper is still called directly
- `qr_queue.py` direct SQL allocators remain separate
- `force_majeure` allocator remains separate
- `OnlineDay` legacy allocators remain separate
- registrar batch/wizard allocator families remain deferred except the mounted
  confirmation bridge that already routes through `VisitConfirmationService`

## Result

The mounted confirmation family is now aligned with the Phase 2 compatibility
boundary:

- corrected confirmation behavior is preserved
- queue allocation creation goes through `QueueDomainService.allocate_ticket()`
- further confirmation-specific allocator work no longer needs to begin from a
  direct legacy service dependency
