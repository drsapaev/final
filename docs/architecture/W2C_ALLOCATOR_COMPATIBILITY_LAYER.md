# Wave 2C Allocator Compatibility Layer

Date: 2026-03-07
Mode: behavior-preserving execution

## Purpose

This document explains the compatibility boundary introduced in Wave 2C Phase 2.

The new public boundary is:

- `QueueDomainService.allocate_ticket()`

This is a facade only. It does not introduce a new numbering algorithm.

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

At the end of Phase 2.1, the boundary is used in:

- characterization tests
- boundary unit tests
- `backend/app/api/v1/endpoints/online_queue_new.py::join_queue()`
- `backend/app/services/qr_queue_service.py::complete_join_session()`
- `backend/app/services/qr_queue_service.py::complete_join_session_multiple()`

This is a limited production rollout.

It is intentionally **not** yet wired into:

- registrar batch writers
- force-majeure allocator paths
- direct SQL allocator branches
- legacy `OnlineDay` callers

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
