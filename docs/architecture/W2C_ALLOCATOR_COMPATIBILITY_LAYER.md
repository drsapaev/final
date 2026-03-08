# Wave 2C Allocator Compatibility Layer

Date: 2026-03-07
Mode: behavior-preserving execution

## Purpose

This document explains the compatibility boundary introduced in Wave 2C Phase 2.

The new public boundary is:

- `QueueDomainService.allocate_ticket()`

This is a facade only. It does not introduce a new numbering algorithm.

Cross-context callers may reach that boundary through:

- `QueueContextFacade`
- `QueueDomainServiceContractAdapter`

## Delegation Rules

`QueueDomainService.allocate_ticket()` currently supports two delegation modes:

### `allocation_mode="create_entry"`

Delegates to:

- `queue_service.create_queue_entry(self.db, **kwargs)`

Use this for current SSOT-style callers that already create queue rows through
the queue service.

### `allocation_mode="join_with_token"`

Delegates to:

- `queue_service.join_queue_with_token(self.db, **kwargs)`

Use this for current online/QR join flows that already rely on token validation,
duplicate checks, and queue-time-window checks inside `queue_service`.

## What The Compatibility Layer Does Not Cover Yet

The boundary does **not** yet absorb:

- direct SQL allocators in `qr_queue.py`
- mixed allocator logic in `qr_queue_api_service.py`
- transfer allocator in `force_majeure_service.py`
- legacy `OnlineDay` / `issue_next_ticket()` paths
- stale `crud/queue.py` ticket path

Those paths remain external migration targets.

## Where The Boundary Is Used Today

After the confirmation migration slice, the boundary is used in:

- characterization tests
- boundary unit tests
- `backend/app/api/v1/endpoints/online_queue_new.py::join_queue()`
- `backend/app/services/qr_queue_service.py::complete_join_session()`
- `backend/app/services/qr_queue_service.py::complete_join_session_multiple()`
- `backend/app/services/visit_confirmation_service.py` for mounted public
  confirmation allocation when a new queue row is needed
- mounted registrar confirmation bridge indirectly through
  `VisitConfirmationService.assign_queue_numbers_on_confirmation()`
- `backend/app/api/v1/endpoints/registrar_integration.py::create_queue_entries_batch()`
  for the mounted batch-only create branch when no active specialist-day claim
  exists

This is a limited production rollout.

It is intentionally **not** yet wired into:

- broader registrar batch/runtime service ownership beyond the mounted create branch
- force-majeure allocator paths
- direct SQL allocator branches
- legacy `OnlineDay` callers
- broader registrar wizard allocator branches outside the mounted confirmation
  bridge

## Why This Shape Is Safe

The boundary is safe because:

- it reuses the existing `queue_service` implementation
- it does not change numbering logic
- it does not change duplicate-policy enforcement
- it does not change `queue_time` semantics
- it does not move direct SQL allocators yet

## Migration Use

This layer is the first execution seam for later phases.

Future migration should replace production callers gradually:

1. caller keeps current behavior
2. caller switches from direct `queue_service` use to `QueueDomainService.allocate_ticket()`
3. only later does the internal allocator implementation change

## Phase 2.1 Outcome

Phase 2.1 narrows the allocator surface area without changing policy:

- thin online join callers now depend on `QueueDomainService`
- QR session completion callers now depend on `QueueDomainService`
- numbering, duplicate detection, and queue-time logic still live in the legacy allocator
- high-risk allocator families remain deferred

## Confirmation Migration Update

The mounted confirmation family now uses the compatibility boundary for queue
row creation while keeping the number lookup helper unchanged:

1. `queue_service.get_next_queue_number(...)`
2. `QueueContextFacade.allocate_ticket(...)`
3. `QueueDomainService.allocate_ticket(...)`
4. legacy `queue_service.create_queue_entry(...)`

This preserves the corrected confirmation behavior while removing the direct
confirmation-family dependency on legacy queue-row creation.

## Registrar Batch Migration Update

Mounted registrar batch-only flow now uses the compatibility boundary for the
create branch only:

1. mounted batch duplicate gate / reuse logic
2. `QueueDomainService.allocate_ticket(...)`
3. legacy `queue_service.create_queue_entry(...)`

This keeps:

- active-row reuse in the mounted path
- explicit `409` ambiguity handling in the mounted path
- numbering and fairness inside the legacy allocator
