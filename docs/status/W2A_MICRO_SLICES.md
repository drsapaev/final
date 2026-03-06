# Wave 2A Micro-Slices

Date: 2026-03-06  
Purpose: identify the few remaining bounded slices that could still move without redesigning queue/payment semantics.

## Candidate Micro-Slices

| ID | Scope | Why it is relatively safe | Recommended track | Execute now? |
|---|---|---|---|---|
| `W2A-MS-011A` | `services.py:resolve_service_endpoint` | Router already has no direct `db.*` calls and existing `ServicesApiService.resolve_service(...)` path exists. Main risk is shared queue taxonomy semantics, not transaction state. | `Wave 2A` | `Conditional yes` |
| `W2A-MS-011B` | `services.py:get_queue_groups` + `get_service_code_mappings` | Read-only metadata builders with no commit/rollback. Existing service methods already exist. | `Wave 2A` or `Wave 2C pre-work` | `Conditional yes` |
| `W2A-MS-090A` | `appointments.py:list_appointments` | Pure read-model endpoint; no transaction writes. Complexity is data shaping, not lifecycle mutation. | `Wave 2B` | `Conditional yes` |
| `W2A-MS-100A` | `admin_stats.py` read-only analytics handlers | Pure reporting queries; no writes or external side effects. | `Wave 2B` or `Wave 2D reporting` | `Conditional yes` |
| `W2A-MS-030A` | `doctor_integration.py:get_doctor_queue_today` | Read-only queue dashboard query. No commit/rollback in router. | `Wave 2C` | `Not before Wave 2C` |
| `W2A-MS-090B` | `appointments.py:get_pending_payments` | Read-only, but crosses appointments, visits, invoices, and payment semantics in one large aggregation. | `Wave 2D` | `No` |

## Micro-Slices Rejected For Now

- `visits.py:set_status` / `reschedule_*`
  - rejected because they mutate both visit and queue state
- `registrar_wizard.py:create_cart_appointments`
  - rejected because it spans visits, queue entries, invoice creation, and payment setup
- `qr_queue.py:full_update_online_entry`
  - rejected because it is a queue state machine, not a cleanup slice
- `cashier.py:create_payment` / `refund_payment`
  - rejected because payment reconciliation is a dedicated track

## Recommendation

- If the user wants one more bounded Wave 2A slice, prefer `W2A-MS-011A` first.
- If the user wants architectural momentum over another tiny slice, stop Wave 2A and open Wave 2C / Wave 2D planning.
