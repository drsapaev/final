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

### Phase 3: Gradually migrate callers

Preferred early caller families:

- SSOT queue-service-backed online join
- registrar batch path
- confirmation path that already relies on SSOT queue models

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

The incorrect first execution target would be:

- replacing scattered allocators directly in routers without the owner contract
