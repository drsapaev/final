# Wave 2C Queue Discovery

Date: 2026-03-06
Mode: analysis-first, docs-only
Scope: backend queue lifecycle only

## Executive Summary

The current queue architecture is split across two implementations:

1. SSOT queue models and services around `DailyQueue` and `OnlineQueueEntry`
2. Legacy department/day queue flow around `OnlineDay` and `Setting(category="queue")`

Queue lifecycle behavior is not centralized. Runtime state changes are spread across:

- `qr_queue.py`
- `doctor_integration.py`
- `registrar_integration.py`
- `visits.py`
- `appointments.py`
- `online_queue_new.py`

The repo already contains queue-specific API services and repositories for read endpoints, limits, reorder, position, cabinet info, and QR flows. What is missing is a single domain boundary that owns:

- state transition rules
- active-status definitions
- transaction boundaries across visit + queue changes
- post-commit side effects such as websocket and push notifications

## Execution Update (2026-03-07)

Wave 2C Phase 1 introduced three safe foundations without changing queue mutation
behavior:

- central queue status vocabulary in `backend/app/services/queue_status.py`
- read-only queue boundary in `backend/app/repositories/queue_read_repository.py`
- `QueueDomainService` skeleton in `backend/app/services/queue_domain_service.py`

The first migrated read-only slices are:

- `W2C-MS-001` queue-position status normalization helper wiring
- `W2C-MS-006` queue snapshot/status reads via `QueueDomainService`
- `W2C-MS-003` cabinet info read handlers via `QueueDomainService`
- `W2C-MS-002` narrowed queue-status-with-limits read handler via `QueueDomainService`
- `W2C-MS-004` narrowed queue metadata read handlers in `services.py` via `QueueDomainService`

Runtime mutation ownership is still fragmented exactly as documented below.

## Data Model and Storage Map

| File | Element | Current responsibilities | DB tables used | Queue status interactions | Side effects |
|---|---|---|---|---|---|
| `backend/app/models/online_queue.py` | `DailyQueue` | Canonical per-day queue aggregate for a specialist or queue tag | `daily_queues` | `opened_at` is used as online-registration closed/opened signal | None directly |
| `backend/app/models/online_queue.py` | `OnlineQueueEntry` | Canonical queue entry model with numbering, patient link, visit link, services, status, priority, session | `queue_entries` | Model comment lists `waiting`, `called`, `in_service`, `diagnostics`, `served`, `incomplete`, `no_show`, `cancelled` | None directly |
| `backend/app/models/online_queue.py` | `QueueToken` | QR token lifecycle for joining queues | `queue_tokens` | Indirect: token decides whether queue join is allowed | None directly |
| `backend/app/models/online_queue.py` | `QueueJoinSession` | Two-step QR join session tracking | `queue_join_sessions` | Session statuses are separate from queue statuses: `pending`, `joined`, `expired`, `cancelled` | None directly |
| `backend/app/models/queue_profile.py` | `QueueProfile` | Maps `queue_tag` values to registrar and QR tabs | `queue_profiles` | Indirect: defines queue taxonomy and routing | Frontend/registrar behavior depends on it |
| `backend/app/models/department.py` | `DepartmentQueueSettings` | Queue-level department settings such as type, limits, prefix, auto-close | `department_queue_settings` | Indirect: influences queue open/limit behavior | None directly |
| `backend/app/models/visit.py` | `Visit` | Visit lifecycle model that is coupled to queue lifecycle in several handlers | `visits`, `visit_services` | Visit status is separate (`open`, `closed`, `canceled`, plus runtime drift such as `in_progress`, `completed`) | None directly |
| `backend/app/models/online.py` | `OnlineDay` | Legacy department/day queue model still used by appointments flow | `online_days` | Uses `is_open`, not `opened_at`; legacy counters use `waiting`, `serving`, `done` | Websocket broadcast through legacy service |

## Runtime Flow Matrix

| File | Function / handler | Current responsibilities | DB tables used | Queue status interactions | Side effects |
|---|---|---|---|---|---|
| `backend/app/services/queue_service.py` | `get_or_create_daily_queue`, `get_next_queue_number`, `assign_queue_token`, `join_queue_with_token`, `create_queue_entry` | SSOT queue creation, numbering, token assignment, queue join, queue entry creation | `daily_queues`, `queue_entries`, `queue_tokens`, queue settings | Creates entries as `waiting`; duplicate checks usually treat only `waiting` and `called` as active | Commits; queue token issuance |
| `backend/app/services/queue_service.py` | `update_queue_status`, `validate_status_transition`, `close_queue_entry`, `reorder_queue`, `resolve_conflicts` | Intended queue lifecycle core, but still not implemented | N/A | Missing central transition authority | None yet |
| `backend/app/services/qr_queue_service.py` | `call_next_patient` | Runtime doctor/registrar call-next behavior | `daily_queues`, `queue_entries` | Finds next `waiting` entry and changes it to `called` | Commit; caller later triggers display or push notifications |
| `backend/app/api/v1/endpoints/qr_queue.py` | token/session/join handlers | Active API for QR queue runtime | `queue_tokens`, `queue_join_sessions`, `daily_queues`, `queue_entries` | Creates and mutates queue state through SSOT and direct ORM | Push and display notifications in several handlers |
| `backend/app/api/v1/endpoints/qr_queue.py` | `restore_entry_to_next` | Restores a previously inactive entry to the front of the queue | `queue_entries` | `no_show` or `cancelled` -> `waiting`; sets `priority = 1` | Commit; queue update event |
| `backend/app/api/v1/endpoints/qr_queue.py` | `mark_entry_no_show` | Marks a patient as absent | `queue_entries` | `waiting` or `called` -> `no_show` | Commit; display update |
| `backend/app/api/v1/endpoints/qr_queue.py` | diagnostics handler | Sends patient to diagnostics | `queue_entries` | `called` or `in_service` -> `diagnostics`; stores `diagnostics_started_at` | Commit |
| `backend/app/api/v1/endpoints/qr_queue.py` | `mark_entry_incomplete` | Marks intake as unfinished | `queue_entries` | `called`, `in_service`, or `diagnostics` -> `incomplete`; stores `incomplete_reason` | Commit |
| `backend/app/api/v1/endpoints/qr_queue.py` | `update_online_entry`, `full_update_online_entry`, `cancel_service_in_entry` | Heavy runtime queue mutation and queue-entry rewriting | `queue_entries`, visit-adjacent and payment-adjacent tables in larger paths | Mixed queue lifecycle mutation | Commit/rollback; notifications |
| `backend/app/api/v1/endpoints/doctor_integration.py` | queue dashboard and runtime actions | Doctor-facing queue list, call, start, complete flows | `daily_queues`, `queue_entries`, `visits`, `appointments`, `payments` | Reads `waiting`, `called`, `served`; also writes queue entry as `called`, `in_progress`, `served` | Commit; display websocket; billing side effects in completion path |
| `backend/app/api/v1/endpoints/registrar_integration.py` | `get_today_queues` | Large registrar queue read model | `queue_entries`, `daily_queues`, `visits`, `appointments`, `queue_profiles`, doctor/service tables | Reads queue and visit state together | None direct, but shapes registrar behavior |
| `backend/app/api/v1/endpoints/registrar_integration.py` | `start_queue_visit` | Starts visit handling for queue-backed record | `visits`, `appointments`, payments | Writes visit status `in_progress`; queue and billing meaning are coupled even if queue row is not directly written here | Commit; payment lookup/creation in nearby logic |
| `backend/app/api/v1/endpoints/registrar_integration.py` | `create_queue_entries_batch` | Batch queue creation when registrar adds services | `patients`, `services`, `daily_queues`, `queue_entries` | Creates new `waiting` queue rows; active duplicate detection uses `waiting` and `called` | Batch commit/rollback |
| `backend/app/api/v1/endpoints/visits.py` | `set_status`, `reschedule_visit`, `reschedule_visit_tomorrow` | Visit lifecycle changes with direct queue updates | `visits`, `queue_entries` | Sets linked queue row to `canceled` or `rescheduled` via raw SQL | Commit; no centralized transition validation |
| `backend/app/services/morning_assignment.py` | `ensure_daily_queues_for_all_tags`, `run_morning_assignment` | Pre-creates daily queues and enqueues confirmed visits | `services`, `daily_queues`, `queue_entries`, `visits` | Creates `waiting` entries; sets visit status to `open` after assignment | Single batch commit |
| `backend/app/api/v1/endpoints/queue_position.py` | queue position read and notifications | Read-only queue position plus manual notification endpoints | `queue_entries`, `daily_queues` | Position visibility considers `waiting`, `called`, `in_service`, `diagnostics` | Push notifications |
| `backend/app/services/queue_position_notifications.py` | queue position notifications | Computes queue position and notifies patients | `queue_entries` | Counts only `waiting` entries ahead; ordering is `priority DESC`, then `queue_time ASC` | FCM / notification side effects |
| `backend/app/api/v1/endpoints/queue_reorder.py` | reorder endpoints | Reorder and move queue entries | `queue_entries`, `daily_queues` | Reorder repository treats only `waiting` and `called` as active | Commit; ordering mutation |
| `backend/app/repositories/queue_reorder_api_repository.py` | queue reorder persistence helper | Encapsulates reorder ORM lookups | `queue_entries`, `daily_queues` | `ACTIVE_ENTRY_STATUSES = ["waiting", "called"]` | Commit/rollback helpers |
| `backend/app/api/v1/endpoints/queue_limits.py` | limits and queue status | Queue limits CRUD and read model | queue settings plus queue tables via service layer | Queue-status read uses queue open/limit information | Writes limits in admin flows |
| `backend/app/api/v1/endpoints/queue_cabinet_management.py` | cabinet info | Read/write cabinet metadata for queues | `daily_queues`, doctor tables | Indirect: no queue state mutation, but queue display metadata | Commit on updates |
| `backend/app/services/queue_auto_close.py` | auto-close by time | Closes online registration when time window expires | `daily_queues`, `queue_entries` | Uses `opened_at` as closed marker; counts active entries as `waiting` and `called` | Commit |
| `backend/app/api/v1/endpoints/online_queue_new.py` | alternative online queue API | Thin alternative entrypoint over SSOT | queue tables via service layer | Returns cancellation status as `canceled` | Commit via service |
| `backend/app/api/v1/endpoints/appointments.py` | `open_day`, `close_day`, `stats`, `qrcode` | Legacy online queue administration | `settings`, `online_days` | Uses legacy `is_open`, `waiting`, `serving`, `done` counters | Legacy websocket broadcast |
| `backend/app/services/online_queue.py` | legacy queue service | Legacy department/day queue counters | `online_days`, `settings` | Maintains `waiting`, `serving`, `done`; not aligned with SSOT queue states | Broadcasts queue updates |
| `backend/app/crud/online_queue.py` | transitional CRUD/business mix | Transitional layer still used by several endpoints | `daily_queues`, `queue_entries`, `queue_tokens` | Duplicates some SSOT behavior and keeps drift alive | Commits directly in several paths |

## Queue Status Vocabulary Found in Code

### Canonical SSOT states present in `OnlineQueueEntry` model

- `waiting`
- `called`
- `in_service`
- `diagnostics`
- `served`
- `incomplete`
- `no_show`
- `cancelled`

### Additional status values observed in handlers and services

- `canceled`
- `rescheduled`
- `in_progress`
- `completed`

These extra values matter because they are not consistently treated across:

- duplicate detection
- queue-position visibility
- reorder logic
- queue statistics
- visit/queue coupling

## Architecture Findings

1. Queue lifecycle is split across multiple runtime entrypoints.
2. The repo already has many queue-specific repositories and API services, but no single queue domain service.
3. The meaning of "active queue entry" is inconsistent:
   - duplicate detection and reorder mostly use `waiting` + `called`
   - queue position also includes `in_service` + `diagnostics`
   - session reuse includes `in_service`
4. Visit lifecycle and queue lifecycle are coupled by direct SQL updates in router code.
5. Legacy queue management (`OnlineDay`) still powers part of the appointments flow and does not share the same state model as `OnlineQueueEntry`.
6. Queue completion is not modeled in one place:
   - SSOT service intends `served`
   - statistics still count `completed`
   - some visit flows use `completed`

## What Wave 2C Must Solve

- Define one queue state machine
- Normalize status vocabulary or at least codify aliases
- Move transition validation out of routers
- Make transaction boundaries explicit for visit + queue changes
- Separate read-only queue APIs from queue lifecycle mutation APIs
- Define how legacy `OnlineDay` will coexist during migration
