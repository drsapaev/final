# Wave 2C Allocator Migration Strategy

Date: 2026-03-07
Mode: behavior-preserving execution

## Purpose

This document describes how current allocators should migrate toward the future
single-owner contract.

It is intentionally migration planning only. No runtime change is performed in
this phase.

## Migration Principle

Do not migrate all allocators at once.

Migration must follow this order:

1. characterize runtime behavior with tests
2. define the allocator contract
3. introduce the single owner behind compatibility adapters
4. migrate one caller family at a time
5. remove bypass allocators only after parity is proven

## Path-by-Path Strategy

| Path | Current role | Migration strategy | Risk level |
|---|---|---|---|
| `queue_service` path | Main SSOT-style allocator and entry-creation helper | Convert into internal implementation behind `QueueDomainService.allocate_ticket()` first; keep behavior-compatible adapter during transition | Medium |
| `qr_queue.py` direct SQL allocator | High-risk inline allocator in add-service/update flows | Do not migrate early. First add characterization tests, then replace direct allocation with domain-service orchestration only after duplicate/fairness contract is stable | High |
| Registrar batch path | Modern registrar write path using `create_queue_entry(auto_number=True)` | Repoint registrar application service to `QueueDomainService` once duplicate-policy contract is implemented; preserve current batch semantics during first cut | Medium |
| Registrar legacy count-based path | Older desk path with `start_number + current_count` | Treat as legacy compatibility slice. Replace only after characterization tests prove operator-visible behavior can be preserved or intentionally superseded | High |
| Confirmation flows | Split "get number, then create row" flows | Collapse into domain-service call after the single-owner API exists; remove split allocation from public application services | Medium |
| Force majeure transfer allocator | Exceptional tomorrow-transfer allocator | Keep separate initially, but force it to call the same internal reservation primitive once transfer semantics are modeled | High |
| Legacy `OnlineDay` path | Separate queue-counter world | Freeze behind legacy adapter. Do not mix into the first allocator migration. Migrate or retire only in a dedicated legacy track | Very High |

## Recommended Migration Phases

### Phase 1: Contract + characterization

- completed in Phase 1.5 and 1.6 docs
- characterization tests added before behavior changes

### Phase 2: Introduce compatibility boundary

- `QueueDomainService.allocate_ticket()` exists as the public boundary
- current `queue_service` remains the internal implementation
- no production caller migration yet
- direct SQL and legacy allocators remain untouched

### Phase 2.1: Safe caller migration

Completed in this pass:

- `backend/app/api/v1/endpoints/online_queue_new.py::join_queue()`
- `backend/app/services/qr_queue_service.py::complete_join_session()`
- `backend/app/services/qr_queue_service.py::complete_join_session_multiple()`

Why these callers were safe:

- they already delegated allocator policy to `queue_service.join_queue_with_token()`
- they did not implement direct SQL numbering
- they did not depend on `OnlineDay`
- they did not own numbering or duplicate policy themselves

### Phase 3: Gradually migrate callers

Preferred early caller families:

- SSOT queue-service-backed online join
- registrar batch path only after explicit duplicate-policy review
- confirmation path only after split allocation is collapsed safely

Later only:

- QR full-update / add-service path
- force-majeure transfer path
- doctor/registrar queue lifecycle flows if allocator coupling appears

### Phase 4: Remove legacy allocators

- direct SQL allocator branches in `qr_queue.py`
- legacy registrar count-based allocator
- `OnlineDay`
- `appointments.py` legacy counters
- stale `crud/queue.py`

This phase should not be mixed into the first compatibility-boundary rollout.

## Migration Guardrails

During execution, stop if a proposed allocator change would:

- rewrite `queue_time`
- change duplicate policy without explicit contract adoption
- renumber historical entries
- change restore/reorder semantics
- mix legacy `OnlineDay` replacement into SSOT allocator work

## Migration Verdict

Allocator migration is feasible, but only as a staged domain migration.

The correct first execution target is:

- single-owner introduction behind `QueueDomainService`
- followed by thin caller migration into the compatibility boundary

The incorrect first execution target would be:

- replacing scattered allocators directly in routers without the owner contract

## Phase 2.2 Review Adjustment

Phase 2.2 narrowed the next migration order further.

Current result:

- confirmation split-flow is the closest family to further work, but only after
  a targeted characterization pass
- registrar work must be split into smaller subfamilies before migration
- `qr_queue.py` direct SQL branches remain blocked by transaction-model
  complexity
- force-majeure transfer remains blocked by its own transfer transaction model
- `OnlineDay` remains a separate legacy track

Recommended order after Phase 2.2:

1. confirmation split-flow characterization
2. registrar batch-only preparation
3. registrar wizard family split
4. duplicate or unmounted service ownership cleanup
5. force-majeure characterization expansion
6. `qr_queue.py` direct SQL preparation
7. `OnlineDay` legacy decision track
