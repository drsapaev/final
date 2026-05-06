# Wave 2C Phase 2.1 Safe Callers

Date: 2026-03-07
Mode: behavior-preserving execution

## Selected Callers

| File | Function | Current allocation path | Why safe | Why no behavior drift expected |
|---|---|---|---|---|
| `backend/app/api/v1/endpoints/online_queue_new.py` | `join_queue()` | Direct `queue_service.join_queue_with_token()` | Thin public join endpoint with no local numbering, duplicate, or queue ordering logic | `QueueDomainService.allocate_ticket(allocation_mode="join_with_token")` delegates to the same legacy allocator and preserves the same exception mapping and response shaping |
| `backend/app/services/qr_queue_service.py` | `complete_join_session()` | Direct `queue_service.join_queue_with_token()` after session/token lookup and patient resolution | Service already treats allocator as a single call and keeps post-allocation work limited to session bookkeeping, metrics, and broadcast side effects | Boundary call preserves the same token-based allocator, duplicate handling, queue number assignment, and queue-time behavior |
| `backend/app/services/qr_queue_service.py` | `complete_join_session_multiple()` | Loop of direct `queue_service.join_queue_with_token()` calls with `specialist_id_override` | Multi-specialist QR flow already centralizes allocation in one service and does not run direct SQL allocator logic here | Each iteration can delegate through the boundary without changing per-specialist allocation semantics, duplicate behavior, or response payload shape |

## Explicitly Excluded From Phase 2.1

- `backend/app/api/v1/endpoints/queue.py::join_queue()`:
  mounted only under legacy prefix `/api/v1/queue/legacy`; low-signal deprecated path, not part of main QR/public join coverage for this phase
- `backend/app/api/v1/endpoints/registrar_integration.py::create_queue_entries_batch()`:
  registrar orchestration, batch semantics, and duplicate-policy nuances are above the current safe threshold
- `backend/app/services/queue_batch_service.py::create_entries()`:
  batch write path with broader side effects than a thin caller swap
- `backend/app/services/visit_confirmation_service.py` confirmation queue creation:
  still splits number allocation from row creation
- `backend/app/api/v1/endpoints/registrar_wizard.py` and `backend/app/services/registrar_wizard_api_service.py`:
  mixed allocator patterns and direct model creation
- `backend/app/api/v1/endpoints/qr_queue.py` and `backend/app/services/qr_queue_api_service.py`:
  direct SQL allocator branches
- `backend/app/services/force_majeure_service.py`:
  exceptional transfer allocator with its own numbering semantics
- `backend/app/services/online_queue.py`, `backend/app/api/v1/endpoints/online_queue.py`, `backend/app/services/online_queue_api_service.py`, `backend/app/crud/queue.py`:
  `OnlineDay` / legacy counter world
- `backend/app/services/online_queue_new_api_service.py`:
  unmounted duplicate router-like module; not safe to refactor blindly while `backend/app/api/v1/endpoints/online_queue_new.py` remains the runtime path
