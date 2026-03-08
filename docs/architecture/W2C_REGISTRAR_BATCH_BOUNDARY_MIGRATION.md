# Wave 2C Registrar Batch Boundary Migration

Date: 2026-03-08
Mode: behaviour-preserving migration

## Old Path

Mounted registrar batch-only create branch used:

1. mounted router duplicate gate
2. direct `queue_service.create_queue_entry(...)`

That meant the caller still depended directly on the legacy allocator path even
after the batch-specific contract and behavior correction were already defined.

## New Path

Mounted registrar batch-only create branch now uses:

1. mounted router duplicate gate
2. `QueueDomainService.allocate_ticket(allocation_mode="create_entry", ...)`
3. legacy allocator delegation inside `QueueDomainService`

## Why Behaviour Is Preserved

The migration changes only the caller path.

It does **not** change:

- numbering algorithm
- `queue_time` handling
- fairness ordering
- active-entry reuse logic
- explicit `409` ambiguity handling
- source passthrough semantics

The boundary still delegates internally to the same legacy allocator.

## What Remains Outside The Boundary

Still deferred:

- broader registrar wizard branches
- `queue_batch_service.py` as future runtime seam
- QR direct SQL allocator family
- force-majeure family
- `OnlineDay` legacy family
- legacy count-based registrar paths

## Outcome

Mounted registrar batch-only family is now aligned with the same compatibility
strategy already used by:

- mounted online join
- QR session completion
- mounted confirmation allocation

This narrows the live allocator surface area without redesigning queue
allocation itself.
