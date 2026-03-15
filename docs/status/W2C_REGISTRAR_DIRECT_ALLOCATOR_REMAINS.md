# Wave 2C Registrar Direct Allocator Remains

## Verdict

No production-relevant registrar direct allocator usage remains after the narrow
runtime fix for the mounted `/registrar/batch` create-action branch.

## Former Mounted Remaining Path

The previously remaining mounted registrar path was:

- endpoint:
  [`backend/app/api/v1/endpoints/registrar_batch.py`](C:/final/backend/app/api/v1/endpoints/registrar_batch.py)
  `batch_update_patient_entries()`
- helper:
  [`backend/app/services/batch_patient_service.py`](C:/final/backend/app/services/batch_patient_service.py)
  `_create_entry()`

It used to:

1. import a non-existent `QueueService`;
2. fail before allocation;
3. bypass the supported queue boundary architecture.

It now:

1. resolves its queue target inside `BatchPatientService`;
2. calls `QueueDomainService.allocate_ticket(allocation_mode="create_entry", ...)`;
3. reaches the supported boundary architecture used by the rest of the migrated
   registrar allocator track.

## Production-Relevant Status

Current verdict for registrar production runtime:

- no mounted registrar path is known to bypass `QueueDomainService.allocate_ticket()`
  while still acting as an active queue-allocation entry point;
- no mounted registrar path is still known to depend on the broken
  `QueueService` import.

## Non-Production Direct Allocator Remains

The following registrar-related direct allocator paths still exist, but are not current production entry points:

- [`backend/app/api/v1/endpoints/registrar_wizard.py`](C:/final/backend/app/api/v1/endpoints/registrar_wizard.py)
  `_create_queue_entries()`
- [`backend/app/services/registrar_wizard_api_service.py`](C:/final/backend/app/services/registrar_wizard_api_service.py)
- [`backend/app/services/registrar_integration_api_service.py`](C:/final/backend/app/services/registrar_integration_api_service.py)
- [`backend/app/services/queue_batch_service.py`](C:/final/backend/app/services/queue_batch_service.py)
- [`backend/app/services/registrar_batch_api_service.py`](C:/final/backend/app/services/registrar_batch_api_service.py)

These should be treated as duplicate/unmounted cleanup debt, not as current registrar migration blockers.
