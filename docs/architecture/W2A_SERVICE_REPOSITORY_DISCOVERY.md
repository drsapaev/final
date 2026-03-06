# Wave 2A Service/Repository Discovery

Date: 2026-03-06  
Scope: `backend/app/api/v1/endpoints/**`  
Goal: find API handlers where router layer still owns ORM/session/query logic instead of delegating to service/repository.

## Baseline Method

1. Static AST scan for route handlers (`@router.get/post/put/delete/...`) with direct DB calls (`db.query`, `db.execute`, `db.add`, `db.commit`, `db.refresh`, `db.delete`, `db.rollback`).
2. Manual grouping by protected zones (`auth`, `payments`, `queue`, `EMR`) and execution risk.
3. Cross-check that parallel `*_api_service.py` and `*_api_repository.py` already exist for affected modules.

Result baseline:
- Original first-pass baseline: `11` files / `122` route handlers
- Current remaining router-layer DB anti-pattern: `10` files / `101` route handlers
- Completed safe slices removed direct router DB access from `messages.py`, catalog-only handlers in `services.py`, and safe handlers in `visits.py`
- Existing service/repository scaffolding found for all affected modules: `yes` (but not consistently wired from routers).

## Priority Groups

- Safe non-protected (completed): `messages.py`, catalog-only handlers in `services.py`, read-only + non-queue write handlers in `visits.py`
- Safe non-protected (remaining candidate): none confirmed in current discovery pass
- Touches payments: `cashier.py`, `appointments.py`, `admin_stats.py`, `registrar_wizard.py`
- Touches queue: `registrar_wizard.py`, `registrar_integration.py`, `qr_queue.py`, `admin_departments.py`, `doctor_integration.py`, queue-adjacent handlers in `services.py`, queue-coupled write handlers in `visits.py`
- Touches auth: none in this scan set with direct DB calls at router level
- Touches EMR: none in this scan set with direct DB calls at router level
- Unclear / needs human review: mixed modules where file includes both safe and protected endpoints (`services.py`, `visits.py`)

## Detailed Findings

| File path | Endpoint/function (examples) | Current anti-pattern | Target shape | Risk | Protected zone | Recommended slice order |
|---|---|---|---|---|---|---|
| `backend/app/api/v1/endpoints/messages.py` | `send_message`, `get_conversation`, `send_voice_message`, `upload_file_message` | Router validates recipient, loads ORM entities, writes audit/file/message rows, commits transaction | Router delegates to `MessagesApiService`, DB access via `MessagesApiRepository` | Low | No | 1 |
| `backend/app/api/v1/endpoints/services.py` | catalog handlers: `list_service_categories`, `create_service`, `update_service`, `delete_service`, `list_doctors_temp`; queue-adjacent handlers: `get_queue_groups`, `resolve_service_endpoint`, `get_service_code_mappings` | Router mixed safe catalog CRUD with queue-adjacent lookup logic in one module | Keep catalog handlers on service/repo flow; leave queue-adjacent handlers isolated for separate review | Medium | Partial (queue-adjacent) | 4 |
| `backend/app/api/v1/endpoints/visits.py` | read-only handlers: `list_visits`, `get_visit` | Router built reflected tables, executed selects, and returned mapped rows directly | Router delegates to `VisitsApiService`, DB access via `VisitsApiRepository` | Low | No | 5 |
| `backend/app/api/v1/endpoints/visits.py` | remaining queue-coupled writes: `set_status`, `reschedule_visit`, `reschedule_visit_tomorrow` | Router updates visit state and queue state in the same handler | Encapsulate queue-aware transaction flow in service/repository only after explicit review | High | Yes (queue) | Pending human review |
| `backend/app/api/v1/endpoints/admin_departments.py` | `create_department`, `update_queue_settings`, `initialize_department` | Router contains multi-step writes and queue/registration settings persistence | Router thin, orchestration in service, DB in repository | High | Yes (queue) | Pending human review |
| `backend/app/api/v1/endpoints/doctor_integration.py` | `get_doctor_queue_today`, `complete_patient_visit`, `schedule_next_visit` | Router mixes queue flow orchestration + transaction logic | Move flow orchestration to service layer | High | Yes (queue) | Pending human review |
| `backend/app/api/v1/endpoints/registrar_integration.py` | `create_registrar_appointment`, `start_queue_visit`, `get_today_queues` | Router includes heavy query composition + queue transaction branches | Service orchestrates, repository isolates query builders | High | Yes (queue) | Pending human review |
| `backend/app/api/v1/endpoints/registrar_wizard.py` | `create_cart_appointments`, `mark_visit_as_paid`, `mark_queue_entry_as_paid` | Router owns queue + payment state transitions and commits | Service use-case orchestration with repository adapters | High | Yes (queue + payments) | Pending human review |
| `backend/app/api/v1/endpoints/qr_queue.py` | `full_update_online_entry`, `update_online_entry`, `cancel_service_in_entry` | Router has very dense queue mutation transaction logic | Service transaction orchestration + repository helpers | High | Yes (queue) | Pending human review |
| `backend/app/api/v1/endpoints/cashier.py` | `create_payment`, `confirm_payment`, `refund_payment` | Router performs payment writes and status transitions directly | Service orchestrates payment flow, repository writes | High | Yes (payments) | Pending human review |
| `backend/app/api/v1/endpoints/appointments.py` | `get_pending_payments`, `open_day`, `close_day` | Router contains query/payment-centric reporting logic | Service query orchestration with repository access | High | Yes (payments) | Pending human review |
| `backend/app/api/v1/endpoints/admin_stats.py` | `get_admin_stats`, `get_analytics_overview` | Router aggregates payment/webhook + appointment queries directly | Service-only orchestration, repository-only querying | High | Yes (payments) | Pending human review |

## Recommended Slice Order

1. `W2A-SR-001` messages core router-thinning (`/send`, `/conversations`, `/conversation/{id}`, `/unread`, `/{id}/read`, `/{id}`)
2. `W2A-SR-002` messages media/reaction router-thinning (`/reactions`, `/users/available`, `/send-voice`, `/voice/{id}/stream`, `/upload`)
3. `W2A-SR-003` architecture guard for router DB anti-patterns in completed module(s)
4. `W2A-SR-010` services catalog-only handlers
5. `W2A-SR-012` visits read-only handlers (`list_visits`, `get_visit`)
6. `W2A-SR-013` visits non-queue writes (`create_visit`, `add_service`) if audit/transaction scope stays local
7. `W2A-SR-011+` mixed/queue-adjacent modules only after explicit human review

## Zones Deferred From Wave 2A Initial Pass

- Queue-heavy modules: `registrar_*`, `qr_queue`, `doctor_integration`, queue-related parts of `services.py`, `visits.py`, `admin_departments.py`
- Payment-heavy modules: `cashier.py`, `appointments.py` payment endpoints, `admin_stats.py`, payment paths in `registrar_wizard.py`
- Any slice requiring changes in protected modules is deferred to `pending human review`.

## Human Review Pass Outcome

- `W2A-SR-011` is no longer a generic cleanup slice; it is queue-adjacent metadata with a small read-only micro-slice candidate.
- `W2A-SR-040` is queue-coupled and transaction-critical; it should not be auto-refactored.
- No broad non-protected slice remains after `W2A-SR-013`.
- Remaining work naturally separates into:
  - `Wave 2C` queue lifecycle
  - `Wave 2D` payment flow hardening
  - a few read-only micro-slices that can still be handled under `Wave 2A` or `Wave 2B`
