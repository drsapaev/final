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

At the end of Phase 2, the boundary is used in:

- characterization tests
- boundary unit tests

It is **not yet wired into production call sites**.

This is intentional. The goal of Phase 2 is to establish the public boundary
without changing runtime behavior.

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
