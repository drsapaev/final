# Wave 2C Registrar Batch Inventory

Date: 2026-03-07
Mode: characterization-first, docs-only
Scope: registrar batch-only allocator subfamily

## In-Scope Runtime Entry

Mounted runtime entry:

- `POST /api/v1/registrar-integration/queue/entries/batch`
- file: `backend/app/api/v1/endpoints/registrar_integration.py`
- function: `create_queue_entries_batch()`

Out of scope:

- registrar confirmation bridge
- broader registrar wizard/cart flow
- `qr_queue.py` direct SQL allocator family
- `OnlineDay` legacy allocators
- `force_majeure` allocator paths

## Inventory Table

| File | Function / element | Role in flow | Inputs | Outputs | Numbering occurs | Duplicate checks occur | Queue entry created | Visit link updated | Billing/payment side effects |
|---|---|---|---|---|---|---|---|---|---|
| `backend/app/api/v1/endpoints/registrar_integration.py` | `create_queue_entries_batch()` | Mounted runtime batch allocator endpoint | `patient_id`, `source`, `services[]` | `success`, `entries[]`, `message` | Yes, via `queue_service.create_queue_entry(auto_number=True)` | Yes, router-level pre-check by `patient_id + specialist/day + waiting/called` | Yes | No | No direct billing/payment side effects |
| `backend/app/services/queue_service.py` | `create_queue_entry()` | Internal SSOT allocator used by batch endpoint | `daily_queue`, patient fields, `source`, `queue_time`, `auto_number` | `OnlineQueueEntry` | Yes, when `number is None or auto_number=True` | No canonical patient duplicate gate in this call pattern | Yes | No | No |
| `backend/app/services/queue_session.py` | `get_or_create_session_id()` | Side effect used during queue-row creation | `patient_id`, `queue_id`, `queue_day` | `session_id` | No | Reuses existing session for `waiting/called/in_service` | No | No | No |
| `backend/app/services/queue_batch_service.py` | `create_entries()` | Cleaner batch application-service seam, but not mounted in current runtime | same batch request semantics | `QueueBatchResult` | Yes, through `queue_service.create_queue_entry()` | Yes, repository-level `patient_id + specialist/day + waiting/called` | Yes | No | No direct billing/payment side effects |
| `backend/app/repositories/queue_batch_repository.py` | `resolve_specialist_user_id()` | Batch-only specialist normalization helper | `specialist_id` | `(user_id, converted)` | No | No | No | No | No |
| `backend/app/repositories/queue_batch_repository.py` | `find_existing_active_entry()` | Batch-only duplicate lookup helper | `specialist_id`, `day`, `patient_id` | existing `OnlineQueueEntry` or `None` | No | Yes, but only `waiting/called` | No | No | No |
| `backend/app/repositories/queue_batch_repository.py` | `get_or_create_daily_queue()` | Batch-only queue resolution helper | `day`, `specialist_id` | `DailyQueue` | No | No | No | No | No |
| `backend/app/services/registrar_integration_api_service.py` | `create_queue_entries_batch()` | Unmounted duplicate route using `QueueBatchService` | same endpoint payload | same response shape | Yes, indirectly | Yes, indirectly | Yes | No | No direct billing/payment side effects |

## Runtime Notes

### 1. Mounted vs unmounted drift

The mounted runtime still uses router-level ORM logic in
`backend/app/api/v1/endpoints/registrar_integration.py`.

A cleaner service/repository version already exists in:

- `backend/app/services/queue_batch_service.py`
- `backend/app/repositories/queue_batch_repository.py`
- `backend/app/services/registrar_integration_api_service.py`

But that path is not mounted in `backend/app/api/v1/api.py`.

### 2. `specialist_id` input is runtime-ambiguous

The schema documents `specialist_id` as `users.id`, but the mounted runtime also
accepts `doctors.id` and converts it to `user_id`.

### 3. Batch-only flow is queue-focused, not visit-focused

This subfamily:

- creates or reuses queue rows
- does not create or update visits
- does not attach services to visits
- does not perform direct billing/payment actions

### 4. Source ownership is caller-driven

Mounted runtime preserves request `source` on newly created queue rows.

Observed accepted values in the current schema/runtime:

- `online`
- `desk`
- `morning_assignment`

### 5. Existing entry reuse is status-sensitive

Mounted runtime reuses only entries with statuses:

- `waiting`
- `called`

It does not treat broader canonical active statuses such as `diagnostics` as a
duplicate-blocking state.
