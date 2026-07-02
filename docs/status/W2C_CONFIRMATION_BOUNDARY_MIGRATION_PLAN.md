# Wave 2C Confirmation Boundary Migration Plan

Date: 2026-03-07
Mode: behaviour-preserving, small diff

## Files In Scope

- `backend/app/services/visit_confirmation_service.py`
- `backend/app/repositories/visit_confirmation_repository.py` only if helper
  support is required
- `backend/app/api/v1/endpoints/registrar_wizard.py` confirmation bridge only
- confirmation-related tests
- confirmation migration/status docs

## Why This Slice Is Safe

- mounted confirmation family already has corrected reuse-existing-entry logic
- ambiguity handling is already explicit and characterized
- `QueueDomainService.allocate_ticket()` already exists as a compatibility
  boundary for `allocation_mode="create_entry"`
- the migration can replace only the caller path while preserving legacy
  allocator internals

## Why This Should Be Behaviour-Preserving

- reuse-existing-entry branch remains unchanged
- ambiguity still returns explicit conflict
- no-active-entry branch still uses legacy numbering inputs
- queue numbering algorithm is not redesigned
- `queue_time` and fairness ordering remain unchanged

## Explicitly Out Of Scope

- `qr_queue.py` direct SQL allocator branches
- `OnlineDay` and legacy queue allocators
- `force_majeure` allocator paths
- broad registrar family changes outside confirmation bridge
- allocator ownership redesign
- duplicate-policy redesign outside confirmation slice

## Old Path

Mounted confirmation family when no active row existed:

1. `queue_service.get_next_queue_number(...)`
2. direct `queue_service.create_queue_entry(...)`

## Planned New Path

Mounted confirmation family when no active row exists:

1. `queue_service.get_next_queue_number(...)` remains legacy
2. `QueueContextFacade.allocate_ticket(...)`
3. `QueueDomainService.allocate_ticket(allocation_mode="create_entry", ...)`

## Reason Legacy Helper May Remain

`QueueDomainService.allocate_ticket()` currently wraps queue-row creation, not
standalone number reservation. Therefore the direct number lookup helper may
remain temporarily until a later allocator-internal migration.

## Context-Boundary Note

The mounted confirmation family should not import `QueueDomainService`
directly. It must reach the queue boundary through the allowed context facade
seam to preserve the architecture boundary guard.
