# Wave 2C Registrar Batch Create-Action Inventory

## Mounted Path

- Endpoint:
  [`backend/app/api/v1/endpoints/registrar_batch.py`](C:/final/backend/app/api/v1/endpoints/registrar_batch.py)
  `batch_update_patient_entries()`
- Mounted through:
  [`backend/app/api/v1/api.py`](C:/final/backend/app/api/v1/api.py)
  `api_router.include_router(registrar_batch.router, prefix="/registrar", tags=["registrar-batch"])`

## Request Shape

The create-action path is entered through:

- `PATCH /api/v1/registrar/batch/patients/{patient_id}/entries/{date}`
- request body:
  [`BatchUpdateRequest`](C:/final/backend/app/services/batch_patient_service.py)
  with one or more
  [`EntryAction`](C:/final/backend/app/services/batch_patient_service.py)
  items where `action == "create"`

Relevant create fields:

- `service_id`
- `service_code`
- `specialty`
- optionally `doctor_id`

## Create-Action Entry Point

Mounted call chain:

1. [`backend/app/api/v1/endpoints/registrar_batch.py`](C:/final/backend/app/api/v1/endpoints/registrar_batch.py)
   `batch_update_patient_entries()`
2. [`backend/app/services/batch_patient_service.py`](C:/final/backend/app/services/batch_patient_service.py)
   `BatchPatientService.batch_update()`
3. [`backend/app/services/batch_patient_service.py`](C:/final/backend/app/services/batch_patient_service.py)
   `_create_entry()`

## Queue Allocation Step

`_create_entry()` currently does:

1. `from app.services.queue_service import QueueService`
2. `queue_service = QueueService(self.db)`
3. `queue_service.add_to_queue(...)`

This means:

- the mounted create-action path does not use `QueueDomainService.allocate_ticket()`;
- it does not use the registrar batch-only boundary seam;
- it bypasses the already migrated wizard and confirmation families.

## Duplicate Behavior

No registrar-specific duplicate gate is implemented inside this create-action branch before allocator invocation.

Observed runtime implication:

- duplicate semantics are effectively unobservable right now because the path breaks before allocation executes.

## Visit Linkage

No explicit visit-link update happens in `_create_entry()`.

The branch appears queue-entry oriented only:

- create one queue row via legacy queue service API;
- return created entry id in `EntryResult`;
- no explicit visit creation/linking logic is present in this branch.

## Runtime Import Requirement

Yes. `QueueService` import is required at runtime for the mounted create-action branch.

## Current Status

`live-but-broken`

Reason:

- the endpoint is mounted and reachable;
- characterization tests can exercise the branch through the mounted route;
- the branch currently fails at runtime on `QueueService` import before queue allocation semantics become observable.
