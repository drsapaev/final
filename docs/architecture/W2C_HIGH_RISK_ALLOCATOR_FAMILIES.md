# Wave 2C High-Risk Allocator Families

Date: 2026-03-07
Mode: analysis-first, docs-only

## Scope

This document inventories the allocator families that were explicitly deferred in
Wave 2C Phase 2.1 and are not safe for broad migration yet.

## Family Inventory

### 1. Registrar batch and wizard flows

| File | Function or entry point | Current allocator mechanism | Duplicate check mechanism | Transaction boundary | Side effects | Legacy dependencies |
|---|---|---|---|---|---|---|
| `backend/app/api/v1/endpoints/registrar_integration.py` | `create_registrar_appointment()` | Inline `current_count` plus `start_number` and direct `QueueEntry` insert for same-day desk registration | No explicit duplicate guard in the legacy same-day branch | Appointment creation and queue insert are committed in one request-level transaction | Creates same-day queue row and operator-visible printed number | Uses legacy `crud_queue.QueueEntry` model and `doctor.id` based `DailyQueue` creation |
| `backend/app/services/registrar_integration_api_service.py` | `create_registrar_appointment()` | Same `start_number + current_count` legacy allocator path | No explicit duplicate guard in the legacy same-day branch | Same request-level transaction | Same as router mirror | Same as router mirror |
| `backend/app/api/v1/endpoints/registrar_integration.py` | `create_queue_entries_batch()` | Calls `queue_service.create_queue_entry(..., auto_number=True, commit=False)` after explicit lookup of `DailyQueue` | Explicit pre-check by `patient_id + queue_id + status in ("waiting", "called")` | One batch transaction across all specialist groups; final `db.commit()` at end | Auto-creates `DailyQueue`, preserves original `source`, stamps `queue_time` once per batch | Mixed `doctor.id` to `user.id` resolution for `specialist_id` |
| `backend/app/services/queue_batch_service.py` | `create_entries()` | Same queue-service-backed allocator as batch endpoint | Repository lookup by active entry for `patient_id + day + specialist` | Service commits once after all entries; rollbacks on domain or unexpected errors | Same as endpoint, but via repository abstraction | Same mixed specialist identity assumptions |
| `backend/app/api/v1/endpoints/registrar_wizard.py` | `_create_queue_entries()` | Split flow: `queue_service.get_next_queue_number()` then `queue_service.create_queue_entry(number=next_number)` | No explicit duplicate guard before creation | Piggybacks on visit creation flow; catches exceptions per visit | Creates one queue row per queue tag for cart appointments | Uses resource-user fallback and `doctor.id` oriented queue ownership |
| `backend/app/services/registrar_wizard_api_service.py` | `_create_queue_entries()` | Same split allocation path as router mirror | No explicit duplicate guard before creation | Same visit-scoped transaction model | Same as router mirror | Same as router mirror |
| `backend/app/api/v1/endpoints/registrar_wizard.py` | `_assign_queue_numbers_on_confirmation()` | Split flow: `get_next_queue_number()` then manual `OnlineQueueEntry(...)` construction | No explicit duplicate guard | Runs inside confirmation flow and shares commit with visit confirmation | Sets `queue_time`, `session_id`, `source="confirmation"`, creates printable ticket payload | Uses resource-user fallback and mixed `doctor.id` / `user.id` handling |
| `backend/app/services/registrar_wizard_api_service.py` | `_assign_queue_numbers_on_confirmation()` | Same split flow with manual row construction | No explicit duplicate guard | Same as router mirror | Same as router mirror | Same as router mirror |

### 2. Confirmation split-flow

| File | Function or entry point | Current allocator mechanism | Duplicate check mechanism | Transaction boundary | Side effects | Legacy dependencies |
|---|---|---|---|---|---|---|
| `backend/app/api/v1/endpoints/visit_confirmation.py` | `confirm_visit_by_telegram()`, `confirm_visit_by_pwa()`, registrar confirm endpoint | Delegates to service; allocator lives below | None at router level | Router delegates to service transaction | Returns printable ticket payloads and updated visit status | None directly |
| `backend/app/services/visit_confirmation_api_service.py` | `confirm_visit_by_telegram()`, `confirm_visit_by_pwa()`, registrar confirm endpoint | Delegates to `VisitConfirmationService` | None at API-service level | Shared with domain service | Same observable API payloads | None directly |
| `backend/app/services/visit_confirmation_service.py` | `_assign_queue_numbers_on_confirmation()` | Split flow: `queue_service.get_next_queue_number()` followed by `queue_service.create_queue_entry(number=next_number, source="confirmation")` | No explicit duplicate guard before allocation | Confirmation updates `visit.confirmed_at`, `visit.status`, queue inserts, then commits once | Emits queue numbers and printable ticket payloads; flips same-day visits from `confirmed` to `open` | Handles `visit.doctor_id` as either `doctor.id` or legacy `user.id` depending on persisted data |

### 3. `qr_queue.py` direct SQL allocator branches

| File | Function or entry point | Current allocator mechanism | Duplicate check mechanism | Transaction boundary | Side effects | Legacy dependencies |
|---|---|---|---|---|---|---|
| `backend/app/api/v1/endpoints/qr_queue.py` | `full_update_online_entry()` | Two direct SQL branches use `SELECT COALESCE(MAX(number), 0) + 1 FROM queue_entries WHERE queue_id = :qid`; one later branch uses `queue_service.get_next_queue_number()` | Not centralized in `queue_service.check_uniqueness()`; relies on aggregated entry grouping, `session_id`, visit linkage, and request-shape decisions | Large multi-model transaction with repeated `flush()`, final `commit()`, and explicit `rollback()` on error | Can create `DailyQueue`, create independent queue entries, create temp patients, create or update `Visit`, update `VisitService`, inspect paid invoices, and sync `all_free` flows | Mixed `specialist_id` ownership, queue-tag-based queue selection, and runtime drift around status vocabulary |
| `backend/app/services/qr_queue_api_service.py` | `full_update_online_entry()` | Mirror of router implementation, including direct SQL `MAX(number)+1` branches | Same as router mirror | Same as router mirror | Same as router mirror | Same as router mirror |

### 4. Force majeure allocator paths

| File | Function or entry point | Current allocator mechanism | Duplicate check mechanism | Transaction boundary | Side effects | Legacy dependencies |
|---|---|---|---|---|---|---|
| `backend/app/services/force_majeure_service.py` | `transfer_entries_to_tomorrow()` | Calls private `_get_next_queue_number()` once, then increments the local `next_number` counter in memory | None before creating tomorrow entries | Creates replacement entries, marks old entries cancelled, `flush()`es, commits once, then sends notifications | Resets `queue_time`, sets `priority` to transfer priority, sets source to `force_majeure_transfer`, sends post-commit notifications | No `OnlineDay` dependency, but it bypasses the main duplicate and fairness contracts |
| `backend/app/services/force_majeure_service.py` | `_get_next_queue_number()` | Reads max active number in target queue and returns `max + 1` | None | Shares transaction context with caller | None directly | Filters out `cancelled` only, which diverges from documented inactive-status contract |

### 5. `OnlineDay` and other legacy allocator paths

| File | Function or entry point | Current allocator mechanism | Duplicate check mechanism | Transaction boundary | Side effects | Legacy dependencies |
|---|---|---|---|---|---|---|
| `backend/app/services/online_queue.py` | `issue_next_ticket()` | Legacy `last_ticket` counter stored in key-value settings, incremented and committed immediately | Identity remembered separately by phone or Telegram mapping | Own commit per ticket issue | Updates stats, writes identity mapping, broadcasts stats | Entirely coupled to `OnlineDay` semantics and morning window rules |
| `backend/app/api/v1/endpoints/online_queue.py` | legacy online queue endpoints | Delegates to `issue_next_ticket()` | Delegates to legacy identity mapping | Uses legacy service transaction | Returns legacy ticket and stats payloads | Full `OnlineDay` dependency |
| `backend/app/services/online_queue_api_service.py` | legacy online queue endpoints | Delegates to `issue_next_ticket()` | Delegates to legacy identity mapping | Same as router mirror | Same as router mirror | Full `OnlineDay` dependency |
| `backend/app/services/queues_api_service.py` | queue dashboard legacy issue path | Delegates to `issue_next_ticket()` | Delegates to legacy identity mapping | Same as legacy service | Returns day stats for old queue board flow | Full `OnlineDay` dependency |
| `backend/app/crud/queue.py` | `next_ticket_and_insert_entry()` | Updates `last_ticket` on legacy table and inserts legacy queue row in one function | None beyond caller logic | Own commit inside helper | Persists `ticket_number` directly | Stale legacy allocator family |

### 6. Unmounted or duplicate queue entry services

| File | Function or entry point | Current allocator mechanism | Duplicate check mechanism | Transaction boundary | Side effects | Legacy dependencies |
|---|---|---|---|---|---|---|
| `backend/app/services/online_queue_new_api_service.py` | `join_queue()` and related router-like handlers | Delegates to `queue_service.join_queue_with_token()` | Delegates to `queue_service.check_uniqueness()` | Same as queue service | Returns public join payloads similar to mounted router | Runtime ownership is ambiguous because this service module is not mounted in `api.py` |
| `backend/app/crud/online_queue.py` | `join_online_queue()` | Standalone `get_next_queue_number()` lookup followed by direct `OnlineQueueEntry` construction | Inline duplicate and max-slot checks, not the canonical queue-service contract | Commits directly after row insert | Increments token usage counter and returns public response payload | Stale helper family still duplicates public join semantics |
| `backend/app/crud/online_queue.py` | `join_online_queue_multiple()` | Repeats `get_next_queue_number()` per specialist and creates direct rows | Inline duplicate and slot checks per target queue | Commits within helper flow | Creates or links patient rows and assigns same logical join across queues | Stale helper family with its own multi-specialist semantics |

## Key Takeaway

The remaining allocator surface is not one family. It is a set of overlapping
families with different ownership assumptions:

- queue-service-backed but split flows
- direct SQL allocators embedded in mutation handlers
- exceptional transfer allocators
- full legacy `OnlineDay` counters
- duplicate or shadow helper modules

That is why a single broad "migrate all callers" step is not safe.
