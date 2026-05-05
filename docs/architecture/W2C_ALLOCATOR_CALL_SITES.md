# Wave 2C Allocator Call Sites

Date: 2026-03-07
Mode: analysis-first, docs-only
Scope: current runtime and legacy allocator call sites

## Purpose

This document records every allocator-adjacent call site that matters for Wave
2C allocator migration.

It is the baseline for introducing a compatibility boundary without changing the
current numbering algorithm or duplicate policy.

## Call Site Map

| File | Function / handler | Allocator logic used | Risk level | Migration priority |
|---|---|---|---|---|
| `backend/app/services/queue_service.py` | `create_queue_entry()` | Calls `get_next_queue_number()` when `number is None` or `auto_number=True` | Medium | P1 |
| `backend/app/services/queue_service.py` | `join_queue_with_token()` | Uses duplicate check + `create_queue_entry(auto_number=True)` | Medium | P1 |
| `backend/app/services/queue_service.py` | `get_next_queue_number()` | SSOT-style `max(number) + 1` allocator | Medium | P1 |
| `backend/app/services/morning_assignment.py` | `_assign_single_queue()` | Delegates to `queue_service.create_queue_entry(auto_number=True)` | Medium | P2 |
| `backend/app/api/v1/endpoints/registrar_integration.py` | `create_queue_entries_batch()` | Duplicate check in router, then `queue_service.create_queue_entry(auto_number=True)` | High | P2 |
| `backend/app/services/queue_batch_service.py` | `create_entries()` | Delegates to `queue_service.create_queue_entry()` | Medium | P2 |
| `backend/app/services/visit_confirmation_service.py` | confirmation queue creation | Calls `get_next_queue_number()` first, then `create_queue_entry(number=...)` | High | P2 |
| `backend/app/api/v1/endpoints/registrar_wizard.py` | queue creation branches | Calls `get_next_queue_number()` and then `create_queue_entry()` or direct model creation | High | P3 |
| `backend/app/services/registrar_wizard_api_service.py` | queue creation branches | Calls `get_next_queue_number()` and then `create_queue_entry()` or direct model creation | High | P3 |
| `backend/app/crud/online_queue.py` | online join helpers | Calls `get_next_queue_number()` then creates `OnlineQueueEntry(number=...)` directly | High | P3 |
| `backend/app/api/v1/endpoints/queue.py` | deprecated `/queue/join` | Calls `queue_service.join_queue_with_token()` | Medium | P2 |
| `backend/app/api/v1/endpoints/online_queue_new.py` | online join | Calls `queue_service.join_queue_with_token()` | Medium | P2 |
| `backend/app/services/qr_queue_service.py` | `complete_join_session*()` | Calls `queue_service.join_queue_with_token()` | Medium | P2 |
| `backend/app/api/v1/endpoints/qr_queue.py` | `full_update_online_entry()` branches | Direct SQL `SELECT COALESCE(MAX(number), 0) + 1` in some branches; `get_next_queue_number()` in another | Very High | P4 |
| `backend/app/services/qr_queue_api_service.py` | service-layer mirror of `full_update_online_entry()` | Same mixed direct-SQL and service allocator split | Very High | P4 |
| `backend/app/services/force_majeure_service.py` | `_get_next_queue_number()` and `transfer_entries_to_tomorrow()` | Separate transfer allocator ignoring `cancelled` rows | High | P4 |
| `backend/app/services/online_queue.py` | `issue_next_ticket()` | Legacy `OnlineDay` / `last_ticket` counter | Very High | P5 |
| `backend/app/api/v1/endpoints/online_queue.py` | legacy queue endpoints | Delegates to `issue_next_ticket()` | Very High | P5 |
| `backend/app/services/online_queue_api_service.py` | legacy service-layer endpoints | Delegates to `issue_next_ticket()` | Very High | P5 |
| `backend/app/crud/queue.py` | `next_ticket_and_insert_entry()` | Stale legacy ticket counter path | Very High | P5 |

## Migration Priority Legend

- `P1`: canonical allocator owner path
- `P2`: compatibility-boundary candidates that already rely on SSOT queue models
- `P3`: split-flow callers that still separate number allocation from row creation
- `P4`: high-risk mixed or exceptional allocators
- `P5`: legacy-only allocators outside first migration pass

## Immediate Phase 2 Outcome

Wave 2C Phase 2 introduces a public boundary in `QueueDomainService`, but this
document intentionally keeps most production callers unchanged.

That means:

- call sites are now mapped
- behavior is characterized with tests
- only the compatibility boundary is added
- direct SQL and legacy allocators remain in place for now

## Explicit Non-Finding

`doctor_integration.py` was checked during this pass. No direct allocator call
site was found there in the current runtime. Its queue complexity is currently
about lifecycle/status orchestration rather than ticket assignment.
