# Wave 2A Domain Flow Analysis

Date: 2026-03-06  
Mode: analysis-first, docs-only  
Purpose: classify remaining router-layer DB access by domain flow before any further refactor.

## Review Scope

- Primary target slices:
  - `W2A-SR-011` (`services.py` queue-adjacent metadata handlers)
  - `W2A-SR-040` (`visits.py` queue-coupled write handlers)
- Additional review set:
  - queue state handlers
  - visit lifecycle handlers
  - registrar/payment orchestration handlers
  - admin reporting/query handlers that still live in routers

## Handler Matrix

| Slice / Area | File | Handler | DB operations | Transaction boundary | Side effects | Queue interactions | Payment interactions | Risk |
|---|---|---|---|---|---|---|---|---|
| `W2A-SR-011` | `backend/app/api/v1/endpoints/services.py` | `get_queue_groups` | `db.query(Service)` read-only enrichment over static `QUEUE_GROUPS` | None in router | Builds frontend/registrar queue metadata payload | Maps `service_code -> group -> queue_tag/tab` | None | Medium |
| `W2A-SR-011` | `backend/app/api/v1/endpoints/services.py` | `resolve_service_endpoint` | No direct `db.*` in router; delegates to `resolve_service(service_id, code, db)` | None in router | Resolves normalized code/category/UI type | Indirect, because result feeds queue grouping and registrar tabs | None | Low to Medium |
| `W2A-SR-011` | `backend/app/api/v1/endpoints/services.py` | `get_service_code_mappings` | `db.query(Service)` read-only enrichment over static mappings | None in router | Builds frontend service-code lookup tables | Enriches `queue_tag -> service_code` mapping | None | Medium |
| `W2A-SR-040` | `backend/app/api/v1/endpoints/visits.py` | `set_status` | `db.query(Visit)`, raw `db.execute(...)` on `queue_entries`, `db.commit`, `db.refresh` | Single commit after visit update plus optional queue update | Mutates visit lifecycle timestamps and status | Cancels linked queue entry when visit becomes `canceled` | None | High |
| `W2A-SR-040` | `backend/app/api/v1/endpoints/visits.py` | `reschedule_visit` | reflected-table `db.execute(select/update)`, `db.commit` | Single commit after visit-date update plus queue status update | Moves visit date | Marks linked queue entry as `rescheduled` | None | High |
| `W2A-SR-040` | `backend/app/api/v1/endpoints/visits.py` | `reschedule_visit_tomorrow` | reflected-table `db.execute(select/update)`, `db.commit` | Same as `reschedule_visit` | Moves visit to tomorrow | Marks linked queue entry as `rescheduled` | None | High |
| Queue config | `backend/app/api/v1/endpoints/admin_departments.py` | `create_department` | `db.query`, `db.add`, `db.flush`, two `db.commit` calls, `db.refresh` | Split transaction boundary: department commit first, queue/reg settings commit second | Boots department integrations and default queue/registration settings | Creates queue settings and registrar settings | None | High |
| Queue config | `backend/app/api/v1/endpoints/admin_departments.py` | `initialize_department` | `db.query`, `db.add`, `db.commit`, `db.rollback` | Single try/commit with rollback on failure | Creates missing queue settings, registration settings, optional service + department binding | Yes, queue settings bootstrap | None | High |
| Queue config | `backend/app/api/v1/endpoints/admin_departments.py` | `update_queue_settings` | `db.query`, optional `db.add`, `db.commit`, `db.refresh` | Simple single commit | Updates department queue policy/config | Directly mutates queue settings | None | Medium |
| Doctor queue | `backend/app/api/v1/endpoints/doctor_integration.py` | `get_doctor_queue_today` | `db.query(...)` read-only joins/lookups | None in router | Builds doctor dashboard payload | Reads queue state and visit status for doctor-facing queue | None | Medium |
| Doctor lifecycle | `backend/app/api/v1/endpoints/doctor_integration.py` | `complete_patient_visit` | many `db.query`, `db.commit`, `db.refresh`, `db.rollback` branches | Multi-branch transaction logic; commit path depends on visit/appointment/queue-entry branch | Completes visit/appointment, may create payment via `BillingService`, may create/update visit from queue entry | Serves queue entry and reconciles queue-derived visit state | Yes, may create/reconcile payment state | Very High |
| Doctor lifecycle | `backend/app/api/v1/endpoints/doctor_integration.py` | `schedule_next_visit` | `db.query`, `db.add`, `db.flush`, `db.commit`, `db.refresh`, `db.rollback` | Multi-step write with rollback | Creates next visit / follow-up scheduling data | Indirect, because follow-up scheduling feeds queue/visit lifecycle | None direct in router | High |
| Registrar flow | `backend/app/api/v1/endpoints/registrar_integration.py` | `create_registrar_appointment` | `db.query`, `db.add`, `db.commit`, `db.refresh` | Single commit, but domain flow spans appointment + queue/profile context | Creates registrar-facing appointment | Appointment participates in queue/registrar flow | Indirect payment readiness | High |
| Registrar flow | `backend/app/api/v1/endpoints/registrar_integration.py` | `start_queue_visit` | `db.query`, `db.commit`, `db.refresh` | Single commit after queue/visit transition | Starts queue-backed visit | Direct queue state transition to in-progress | Payment state is read/derived in nearby flow | High |
| Registrar flow | `backend/app/api/v1/endpoints/registrar_integration.py` | `get_today_queues` | `db.query`, `db.execute` in a very large read-model handler | None in router | Builds large registrar dashboard/read model | Reads queue, visit, appointment, doctor, queue-profile state | Includes payment-derived status shaping | High |
| Registrar flow | `backend/app/api/v1/endpoints/registrar_integration.py` | `create_queue_entries_batch` | `db.query`, `db.add`, `db.flush`, `db.commit`, `db.rollback` | Batch write transaction | Creates multiple queue entries/tickets in one request | Direct queue creation | None direct in router | Very High |
| Registrar checkout | `backend/app/api/v1/endpoints/registrar_wizard.py` | `init_invoice_payment` | `db.query(PaymentInvoice)`, `db.commit` | Single commit after external provider init | Calls payment provider, updates invoice to `processing` | None direct | Yes, external Click/PayMe initiation | High |
| Registrar checkout | `backend/app/api/v1/endpoints/registrar_wizard.py` | `check_invoice_status` | `db.query`, `db.commit` | Single commit after provider check, but external state drives local mutation | Calls payment provider status API, updates invoice, may create payments via `BillingService` | None direct | Yes, provider + invoice + billing reconciliation | Very High |
| Registrar checkout | `backend/app/api/v1/endpoints/registrar_wizard.py` | `create_cart_appointments` | `db.query`, `db.add`, `db.flush`, `db.commit`, `db.rollback` | Large multi-entity transaction | Creates visits, services, queue entries, invoice/payment context, price overrides | Yes, queue entries created | Yes, invoice/payment path created | Very High |
| Registrar checkout | `backend/app/api/v1/endpoints/registrar_wizard.py` | `mark_visit_as_paid` | `db.query`, `db.execute`, `db.commit`, `db.refresh`, `db.rollback` | Single commit but payment status drives visit mutation | Marks visit paid | Indirect via visit lifecycle | Yes | Very High |
| Registrar checkout | `backend/app/api/v1/endpoints/registrar_wizard.py` | `mark_queue_entry_as_paid` | `db.query`, `db.execute`, `db.commit`, `db.refresh`, `db.rollback` | Single commit but queue + payment state change together | Marks queue-backed visit as paid | Yes, queue entry linked to payment status | Yes | Very High |
| Cashier | `backend/app/api/v1/endpoints/cashier.py` | `create_payment` | `db.query(Visit/Payment)`, `db.add(Payment)`, `db.commit`, `db.refresh`, `db.rollback` | Single commit with rollback | Creates payment and broadcasts cashier websocket event | Indirect via visit debt/status | Yes | Very High |
| Cashier | `backend/app/api/v1/endpoints/cashier.py` | `confirm_payment` | `db.query`, `db.add`, `db.commit` | Single commit | Confirms existing payment | Indirect via visit/payment reconciliation | Yes | High |
| Cashier | `backend/app/api/v1/endpoints/cashier.py` | `refund_payment` | `db.query`, `db.add`, `db.commit`, `db.refresh`, `db.rollback` | Single commit with rollback | Refunds payment and mutates visit/payment state | Indirect via visit state rollback | Yes | Very High |
| Cashier | `backend/app/api/v1/endpoints/cashier.py` | `mark_visit_as_paid` | `db.query`, `db.add`, `db.commit`, `db.rollback` | Single commit with rollback | Marks visit paid from cashier side | Indirect via visit state | Yes | Very High |
| Queue runtime | `backend/app/api/v1/endpoints/qr_queue.py` | `call_next_patient` | router does `db.query(OnlineQueueEntry)` for notifications; mutation happens inside `QRQueueService.call_next_patient(...)` | Effective transaction is inside service, not visible at router | Sends user notification and display websocket event | Yes, advances queue state to next patient | None direct | High |
| Queue runtime | `backend/app/api/v1/endpoints/qr_queue.py` | `update_online_entry` | `db.query`, `db.commit`, `db.refresh` | Single commit | Mutates one online queue entry | Yes | None | High |
| Queue runtime | `backend/app/api/v1/endpoints/qr_queue.py` | `full_update_online_entry` | `db.query`, `db.execute`, `db.add`, `db.flush`, `db.commit`, `db.refresh`, `db.rollback` | Large multi-step transaction | Rewrites queue entry, visit/payment/state links | Yes, heavy queue lifecycle mutation | May touch payment/status side effects | Very High |
| Queue runtime | `backend/app/api/v1/endpoints/qr_queue.py` | `cancel_service_in_entry` | `db.query`, `db.commit`, `db.refresh`, `db.rollback` | Single commit with rollback | Cancels service inside queue entry | Yes | None direct | High |
| Mixed read model | `backend/app/api/v1/endpoints/appointments.py` | `list_appointments` | `db.query(Appointment/Patient/Service)` read-only enrichment | None in router | Builds appointment list with patient/service names | None direct | Indirect, because payment amounts are exposed in response | Medium |
| Mixed read model | `backend/app/api/v1/endpoints/appointments.py` | `get_pending_payments` | many `db.query(...)` over appointments, visits, invoices, services | None in router | Builds pending-payments unified dashboard payload | Reads queue-adjacent visit status | Yes, direct pending-payment aggregation | High |
| Queue admin | `backend/app/api/v1/endpoints/appointments.py` | `open_day` | `_upsert_queue_setting(...)`, `db.commit` | Single commit | Writes queue day settings and triggers `_broadcast(...)` | Yes, opens online queue day | None | High |
| Queue admin | `backend/app/api/v1/endpoints/appointments.py` | `close_day` | `get_or_create_day(...)`, `db.commit` | Single commit | Closes queue day | Yes | None | Medium to High |
| Analytics | `backend/app/api/v1/endpoints/admin_stats.py` | `get_admin_stats` | many `db.query(...).count()/scalar()` read-only queries | None in router | Builds admin summary metrics | Indirect via visits/appointments counts | Direct revenue/payment summary | Medium |
| Analytics | `backend/app/api/v1/endpoints/admin_stats.py` | `get_recent_activities` | many `db.query(...)` read-only queries | None in router | Builds combined activity feed from appointments, payments, users | Indirect via visit/appointment status strings | Direct payment activity feed | Medium |
| Analytics | `backend/app/api/v1/endpoints/admin_stats.py` | `get_analytics_overview` | many `db.query(...)`, in-memory aggregation | None in router | Builds filtered analytics overview and doctor leaderboard | Indirect via appointment state | Direct payment aggregation | Medium |

## Observations

1. `W2A-SR-011` is queue-adjacent, but its handlers are read-model and metadata focused. The risk is not transaction correctness; the risk is breaking queue taxonomy shared by registrar/frontend flows.
2. `W2A-SR-040` is genuinely transaction-critical. Each handler mutates both visit lifecycle state and queue state inside the same request.
3. The remaining backlog is no longer a generic service/repository cleanup problem. It is mostly domain orchestration:
   - queue lifecycle
   - registrar orchestration
   - payment reconciliation
   - admin read models spanning multiple aggregates
4. Some routers already have service methods implemented (`services_api_service.py`, `visits_api_service.py`), but delegating blindly is not sufficient if the domain boundary is unclear or the service itself still embeds transaction policy.
