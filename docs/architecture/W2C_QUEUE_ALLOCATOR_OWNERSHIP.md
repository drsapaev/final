# Wave 2C Queue Allocator Ownership

Date: 2026-03-07
Mode: analysis-first, docs-only

## Purpose

This document defines who should become the single owner of queue numbering.

It does not change runtime behavior. It defines the target ownership contract
required before any future execution slice touches number allocation.

## Current Allocators

| Allocator path | Current owner | Why it exists today | Main conflict |
|---|---|---|---|
| `queue_service.get_next_queue_number()` + `create_queue_entry()` | `backend/app/services/queue_service.py` | Main SSOT-style queue creation path | Not enforced as the only path |
| Direct SQL `MAX(number)+1` | `backend/app/api/v1/endpoints/qr_queue.py` | QR full-update adds services into queues inline | Bypasses service ownership and duplicate policy ownership |
| `start_number + current_count` | `backend/app/api/v1/endpoints/registrar_integration.py` | Older desk/registrar flow | Uses a separate allocator model |
| Split "ask number, then create row" | `visit_confirmation_service.py`, `registrar_wizard_api_service.py`, transitional CRUD | Confirmation and wizard flows evolved around the old service boundary | Number allocation and row creation can drift apart |
| Transfer allocator | `backend/app/services/force_majeure_service.py` | Tomorrow-transfer flow needed its own helper | Separate queue-life-cycle exception path |
| Legacy `last_ticket` allocator | `backend/app/services/online_queue.py`, `backend/app/api/v1/endpoints/appointments.py` | Legacy department/day queue model | Keeps a second numbering worldview alive |

## Ownership Conflicts

### 1. Number allocation is split across routers, services, and legacy layers

Runtime code currently allows:

- routers to allocate directly
- service helpers to allocate
- transitional CRUD layers to allocate
- legacy queue subsystems to allocate independently

That means there is no single place that can guarantee:

- monotonic numbering
- queue-local uniqueness
- correct duplicate policy
- consistent transaction boundaries

### 2. Allocation is not always tied to entry creation

Some flows do this:

1. get `next_number`
2. later create `OnlineQueueEntry`

That split is acceptable only if one owner still governs both steps. Today that
is not true.

### 3. Duplicate policy is not owned by the allocator

Current duplicate checks live in different places and use different identity
rules. A future allocator owner must either own the duplicate rule directly or
orchestrate the canonical duplicate-policy owner inside the same unit of work.

### 4. Legacy and exceptional flows still need a compatibility story

Even after the single owner is defined, these flows will remain migration
targets:

- QR full-update add-service path
- registrar legacy count-based path
- force-majeure transfer path
- legacy `OnlineDay` counters

## Why A Single Owner Is Required

A single owner is needed because queue numbering is not just a helper function.
It is part of the queue domain contract:

- it decides who gets a new ticket
- it decides when a duplicate should block allocation
- it must preserve `queue_time` fairness semantics
- it must run inside one transaction boundary with queue-entry creation

Without a single owner, future refactors would continue to move logic around
without actually removing policy drift.

## Proposed Single Owner

`QueueDomainService`

### Reasoning

`QueueDomainService` is the correct ownership layer because:

- numbering is a domain policy, not a router concern
- numbering is coupled to duplicate policy
- numbering is coupled to fairness semantics
- numbering is coupled to queue-entry creation transaction boundaries
- repositories should provide persistence primitives, not decide who is allowed
  to receive a ticket

## Proposed Ownership Rule

Only `QueueDomainService` may expose a public numbering operation:

`allocate_ticket()`

Everything else becomes:

- a repository implementation detail
- a compatibility adapter
- or a migration target

## Allowed Lower-Level Helpers

The single-owner rule does **not** mean repositories disappear.

It means repositories may provide internal methods such as:

- `reserve_next_ticket_number(...)`
- `find_existing_active_entry(...)`
- `insert_queue_entry(...)`

But routers and application services must not call those methods directly to
implement queue numbering policy.

## Contract Outcome

### Public owner

- `QueueDomainService.allocate_ticket(...)`

### Internal collaborators

- `QueueRepository` or a dedicated allocator repository for persistence
- duplicate-policy helper/repository under domain-service control
- transaction/unit-of-work boundary under domain-service control

## Phase 1.6 Verdict

Allocator ownership can be defined clearly enough to continue planning.

Decision:

- single owner required: yes
- proposed single owner: `QueueDomainService`
- ready for contract definition: yes
- ready for runtime migration: not yet
