# Wave 2C Safe Slices

Date: 2026-03-06
Mode: analysis-first

## Purpose

These are the safest queue-related refactor slices available after discovery.
They avoid changing queue semantics, payment behavior, and visit lifecycle orchestration.

## Safe Refactor Candidates

| Slice ID | Area | Files | Why it is relatively safe | Tests to run |
|---|---|---|---|---|
| `W2C-MS-001` | Read-only queue position lookup | `backend/app/api/v1/endpoints/queue_position.py`, `backend/app/services/queue_position_api_service.py`, `backend/app/repositories/queue_position_api_repository.py` | Already service/repository-oriented; read path can be normalized without changing mutations | targeted queue-position tests, then `cd backend && pytest -q` |
| `W2C-MS-002` | Queue limits read model | `backend/app/api/v1/endpoints/queue_limits.py`, queue-limits service/repository files | `get_queue_status_with_limits` is mostly read-only; can be used to standardize active-status definitions in one place | targeted limits tests, then `cd backend && pytest -q` |
| `W2C-MS-003` | Queue cabinet read endpoints | `backend/app/api/v1/endpoints/queue_cabinet_management.py`, cabinet service/repository files | Read-only cabinet info endpoints are metadata-oriented and do not change queue lifecycle | targeted cabinet tests, then `cd backend && pytest -q` |
| `W2C-MS-004` | Queue metadata read helpers | `backend/app/api/v1/endpoints/services.py`, `backend/app/services/services_api_service.py`, queue profile/service-mapping helpers | Queue taxonomy is domain-sensitive, but pure read extraction is still safer than lifecycle mutation | targeted service metadata tests, then `cd backend && pytest -q` |
| `W2C-MS-005` | Number-allocation boundary extraction | `backend/app/services/queue_service.py`, future `QueueRepository` | Can centralize `get_next_queue_number` and duplicate-check policy without changing outward API if done behind existing callers | targeted queue numbering tests, then `cd backend && pytest -q` |
| `W2C-MS-006` | Queue snapshot status endpoints | `backend/app/api/v1/endpoints/queue_reorder.py` read status handlers only | `get_queue_status*` can move to a common queue snapshot read boundary without touching reorder writes | targeted reorder-status tests, then `cd backend && pytest -q` |

## Not Safe for the First Queue Refactor Pass

These should not be auto-refactored before the domain service and state machine are agreed.

| Area | Why it is not safe yet |
|---|---|
| `qr_queue.call_next_patient` and runtime mutations | Directly changes queue lifecycle and triggers notifications |
| `qr_queue.mark_entry_no_show`, diagnostics, incomplete, restore | Transition semantics are important and currently scattered |
| `doctor_integration` start/complete flows | Mixes queue, visit, and payment consequences |
| `registrar_integration.start_queue_visit` | Visit lifecycle and payment readiness are coupled |
| `registrar_integration.create_queue_entries_batch` | Batch write with duplicate rules, queue grouping, and fairness timestamps |
| `visits.set_status` and `reschedule_*` | Direct queue SQL mutation tied to visit lifecycle |
| `queue_reorder` write endpoints | Reorder semantics depend on the agreed active-state set |
| Legacy `appointments.open_day/close_day` replacement | Requires a deliberate migration from `OnlineDay` to `DailyQueue` |

## Recommended Order

1. `W2C-MS-001`
2. `W2C-MS-003`
3. `W2C-MS-002`
4. `W2C-MS-006`
5. `W2C-MS-005`

`W2C-MS-004` stays optional because queue taxonomy is queue-domain policy, not just catalog metadata.

## Exit Rule

Stop taking "safe" slices if a proposed change needs any of the following:

- new queue state semantics
- visit lifecycle change
- payment/billing side effect change
- legacy queue migration
- cross-module transaction redesign
