# Wave 2C Online Queue Doc Compliance

Date: 2026-03-07
Mode: document-compliance-first
Normative source: `docs/ONLINE_QUEUE_SYSTEM_IMPLEMENTATION.md`

## Purpose

This document records which queue design principles from
`ONLINE_QUEUE_SYSTEM_IMPLEMENTATION.md` must be preserved during Wave 2C
execution, which ones already match current code, and which ones are already in
drift and therefore require adaptation or human review.

## Compliance Matrix

| Principle | Source location | Affected modules/files | Compliance state | Notes |
|---|---|---|---|---|
| SSOT queue storage uses `DailyQueue`, `OnlineQueueEntry`, `QueueToken`; `queue_time`, `source`, `is_clinic_wide` are first-class fields | "Database", lines 73-131; "AppointmentWizardV2 integration checklist", lines 684-688 | `backend/app/models/online_queue.py`, `backend/app/services/queue_service.py`, `backend/app/api/v1/endpoints/qr_queue.py`, `backend/app/services/morning_assignment.py` | Preserved as-is | Phase 1 may add service/repository boundaries, but it must not replace these models or introduce a second SSOT. |
| Queue priority is determined by `queue_time`; it is fixed at creation and must not change during patient-data edits | "Architecture and principles" > "Priority based on registration time", lines 41-46; "Hybrid editing", lines 55-62; checklist lines 703-704 and 744-745 | `backend/app/services/queue_service.py`, `backend/app/api/v1/endpoints/qr_queue.py`, `backend/app/api/v1/endpoints/registrar_integration.py`, `backend/app/services/morning_assignment.py` | Preserved as-is | This is a hard stop for Phase 1. No refactor may change numbering, sorting, or rewrite `queue_time`. |
| One patient may have multiple queue entries, one per service/specialist; multi-QR registration shares the same `queue_time` across all entries created in that join flow | "Architecture and principles" > "Multiple queues for one patient", lines 48-53; `POST /queue/join/complete`, lines 203-242 | `backend/app/api/v1/endpoints/qr_queue.py`, `backend/app/services/queue_service.py` | Preserved as-is | Phase 1 cannot collapse or merge entries in a way that changes per-service queue ownership. |
| Hybrid edit rule: patient data updates do not change existing queue order; new services create new queue rows with current edit time and go to the tail | "Hybrid editing", lines 55-62; Scenario 3; checklist lines 703-704 and 754-755 | `backend/app/api/v1/endpoints/qr_queue.py`, `backend/app/api/v1/endpoints/registrar_integration.py`, wizard-related backend paths | Preserved as-is | This blocks any mutation refactor in Phase 1 for QR full-update or registrar batch-add flows. |
| QR joins are blocked by `opened_at`, `online_end_time`, and `online_start_time` | "Automatic QR blocking", lines 64-69; "Technical details" > validation rules | `backend/app/services/queue_service.py`, `backend/app/services/qr_queue_service.py`, `backend/app/services/queue_auto_close.py` | Preserved as-is | Phase 1 cannot rewrite open/close semantics. |
| Source ownership is normative: `online`, `desk`, `morning_assignment`; source must be preserved when creating queue entries | "Database" > `OnlineQueueEntry`, lines 80-93; checklist lines 688-699 and 706-709 | `backend/app/services/queue_service.py`, `backend/app/services/morning_assignment.py`, `backend/app/api/v1/endpoints/registrar_integration.py` | Preserved as-is | Phase 1 may centralize helpers, but it must not reinterpret source semantics. |
| QR join flow creates queue entries only; it must not create visits or appointments at join time | Checklist lines 687-688 and 749-750 | `backend/app/api/v1/endpoints/qr_queue.py`, `backend/app/services/queue_service.py` | Preserved as-is | This blocks any attempt to merge queue join with visit lifecycle in Phase 1. |
| Desk flow creates visits through registrar/cart and then assigns queue entries using SSOT path | Checklist lines 690-695 | `backend/app/api/v1/endpoints/registrar_wizard.py`, `backend/app/services/morning_assignment.py`, queue assignment helpers | Preserved as-is | Phase 1 does not touch registrar/cart or desk mutation paths. |
| Morning assignment creates queue entries for confirmed visits with `source='morning_assignment'` and queue time equal to assignment run time | Scenario 6; checklist lines 696-699 and 762-765 | `backend/app/services/morning_assignment.py`, `backend/app/services/queue_service.py` | Needs adaptation | The document claims `DailyQueue.specialist_id` points to `users.id`, while the actual model is `ForeignKey('doctors.id')` and code contains compatibility shims. Phase 1 must not change this behavior; deeper cleanup requires human review. |
| Batch queue creation uses `QueueBusinessService.create_queue_entry()` and sets `queue_time` once, taking `source` from the request | Checklist lines 706-709 | `backend/app/api/v1/endpoints/registrar_integration.py`, `backend/app/services/queue_service.py`, `backend/app/repositories/queue_batch_repository.py` | Preserved as-is | Phase 1 cannot rewrite batch queue creation semantics. |
| Queue status vocabulary in the normative doc is `waiting`, `called`, `completed`, `cancelled` | "Database" > `queue_entries`, line 123 | `backend/app/models/online_queue.py`, `backend/app/services/queue_service.py`, `backend/app/api/v1/endpoints/qr_queue.py`, `backend/app/api/v1/endpoints/doctor_integration.py`, `backend/app/api/v1/endpoints/visits.py` | Conflict | Runtime code already uses additional statuses such as `in_service`, `diagnostics`, `served`, `incomplete`, `no_show`, `canceled`, `rescheduled`, and `in_progress`. Phase 1 may only introduce an alias/normalization layer. It must not change persistence semantics without human review. |
| Queue length and related queue calculations should use `OnlineQueueEntry` rather than mixing `Visit` or `Appointment` | "History" > "Fix queue length calculation", lines 820-824 | `backend/app/services/qr_queue_service.py`, queue read services, queue read repositories | Preserved as-is | Safe read-only slices should continue to use queue tables as the read source. |
| Frontend queue panels rely on unified queue read models and QR/Manual labels derived from `source` | "Frontend" > `ModernQueueManager.jsx`, `EnhancedAppointmentsTable.jsx`, checklist lines 717-744 | `backend/app/api/v1/endpoints/registrar_integration.py`, read-only queue APIs | Preserved as-is | Phase 1 may not change response shape or source labels for read-only slices. |
| Legacy compatibility exists and remains in the system; doc claims SSOT models are required, but runtime still contains legacy `OnlineDay` administration | File changes and existing runtime reality vs. checklist lines 684-685 | `backend/app/api/v1/endpoints/appointments.py`, `backend/app/services/online_queue.py` | Conflict | Phase 1 must not touch legacy migration logic. This mismatch remains pending human review for later phases. |

## Phase 1 Compliance Result

### Allowed under document compliance

- introduce a status normalization helper that does not rewrite stored data
- introduce a `QueueDomainService` skeleton with explicit boundaries
- migrate read-only queue snapshot/status flows
- centralize read-only raw-status lists used by queue read services

### Disallowed under document compliance

- changing queue numbering rules
- changing `queue_time` ownership or fairness
- changing duplicate policy
- changing QR open/close rules
- changing visit-to-queue mutation flows
- migrating legacy `OnlineDay` behavior

## Human Review Flags

The following items are already in doc-vs-code drift and must not be "fixed" silently in
Phase 1:

1. Queue status vocabulary beyond `waiting/called/completed/cancelled`
2. `DailyQueue.specialist_id` semantics (`doctors.id` in model vs `users.id` in parts of the doc)
3. Legacy queue compatibility vs the document's stronger SSOT claim

## Phase 1 Execution Verdict

Execution remained inside the allowed window.

Implemented foundations:

- `backend/app/services/queue_status.py`
- `backend/app/services/queue_domain_service.py`
- `backend/app/repositories/queue_read_repository.py`
- read-only updates in:
  - `backend/app/repositories/queue_position_api_repository.py`
  - `backend/app/repositories/queue_reorder_api_repository.py`
  - `backend/app/services/queue_reorder_api_service.py`

Compliance outcome:

- preserved as-is:
  - SSOT ownership (`DailyQueue`, `OnlineQueueEntry`, `QueueToken`)
  - queue numbering and `queue_time` fairness rules
  - duplicate policy semantics
  - visit-to-queue linkage semantics
  - QR open/close rules
- adapted safely:
  - status vocabulary now has a documented alias layer for internal comparisons
  - queue snapshot/status reads now use an explicit read-only domain boundary
  - cabinet read handlers now use runtime `DailyQueue.specialist_id -> doctors.id` semantics through the queue read boundary
  - queue-limits status read now uses the same runtime-compatible `doctor.user_id` lookup it used before the refactor
  - queue metadata read handlers in `services.py` now use the queue read boundary while preserving static `QUEUE_GROUPS` / `SPECIALTY_ALIASES` semantics and best-effort active-service enrichment
- still in conflict and deferred:
  - status drift beyond the normative four-state vocabulary
  - `doctors.id` vs `users.id` wording drift
  - legacy `OnlineDay` coexistence

No code change in Phase 1 attempted to "fix" those deferred conflicts.
