# Wave 2C Phase 2.1 Deferred Callers

Date: 2026-03-07
Mode: behavior-preserving execution

| File | Function | Reason deferred | Risk type | Suggested later phase |
|---|---|---|---|---|
| `backend/app/api/v1/endpoints/queue.py` | `join_queue()` | Legacy-prefixed route with low current signal; not part of primary QR/public join flow for this pass | Legacy/deprecated path | Review before later safe migration pass |
| `backend/app/services/morning_assignment.py` | `_assign_single_queue()` | `morning_assignment` source semantics and visit-opening flow should be migrated only with dedicated characterization around scheduled queue population | Lifecycle/source semantics | Later safe pass or pre-2C high-risk review |
| `backend/app/api/v1/endpoints/registrar_integration.py` | broader registrar queue creation branches outside mounted batch-only create path | Mounted batch-only create path is migrated, but broader registrar orchestration still mixes allocator behavior with wizard/runtime concerns | Registrar orchestration / mixed logic | Broader registrar family track |
| `backend/app/services/queue_batch_service.py` | `create_entries()` | Batch writer path with broader side effects than thin join callers | Batch write semantics | Review before high-risk allocator migration |
| `backend/app/api/v1/endpoints/registrar_wizard.py` | broader queue creation branches outside mounted same-day create path | Mounted same-day wizard create path is now migrated through the compatibility boundary, but broader wizard/cart orchestration remains deferred | Mixed logic | Broader registrar family track |
| `backend/app/services/registrar_wizard_api_service.py` | queue creation branches | Same mixed allocator behavior as router counterpart | Mixed logic | High-risk allocator migration |
| `backend/app/crud/online_queue.py` | online join helpers | Direct model creation after standalone number lookup | Direct model creation | High-risk allocator migration |
| `backend/app/api/v1/endpoints/qr_queue.py` | `full_update_online_entry()` branches | Direct SQL allocator branches | Direct SQL / numbering semantics | Review before high-risk allocator migration |
| `backend/app/services/qr_queue_api_service.py` | mirror allocator branches | Same mixed direct SQL + service allocator split | Direct SQL / mixed logic | Review before high-risk allocator migration |
| `backend/app/services/force_majeure_service.py` | `_get_next_queue_number()`, `transfer_entries_to_tomorrow()` | Own transfer allocator with separate status and numbering assumptions | Exceptional flow / numbering semantics | Dedicated force-majeure review |
| `backend/app/services/online_queue.py` | `issue_next_ticket()` | `OnlineDay` legacy counter | Legacy/OnlineDay | Legacy migration track |
| `backend/app/api/v1/endpoints/online_queue.py` | legacy online queue endpoints | Delegates to `OnlineDay` counter semantics | Legacy/OnlineDay | Legacy migration track |
| `backend/app/services/online_queue_api_service.py` | legacy online queue endpoints | Delegates to `OnlineDay` counter semantics | Legacy/OnlineDay | Legacy migration track |
| `backend/app/crud/queue.py` | `next_ticket_and_insert_entry()` | Stale legacy ticket path | Legacy/stale allocator | Legacy cleanup track |
| `backend/app/services/online_queue_new_api_service.py` | `join_queue()` and related router-like handlers | Duplicate unmounted module; unsafe to refactor blindly while mounted runtime path lives elsewhere | Shadow/dead-path ambiguity | Human review / cleanup track |

## Superseded by Phase 2.2 Review

This caller list is still valid as a raw deferred inventory, but family-level
readiness and ordering now live in:

- `docs/architecture/W2C_HIGH_RISK_ALLOCATOR_FAMILIES.md`
- `docs/status/W2C_HIGH_RISK_MIGRATION_READINESS.md`
- `docs/architecture/W2C_HIGH_RISK_MIGRATION_ORDER.md`

Mounted confirmation family is no longer deferred. It now uses the compatibility
boundary for queue-row creation.

Mounted registrar batch-only create path is also no longer deferred. It now
uses the compatibility boundary while keeping local reuse/ambiguity logic in
place.
