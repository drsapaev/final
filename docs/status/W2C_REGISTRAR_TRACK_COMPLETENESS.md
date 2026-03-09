# Wave 2C Registrar Track Completeness

## Assessed Families

Completed / effectively covered:

- confirmation family;
- mounted registrar batch-only create family;
- mounted wizard same-day queue-assignment family.

Still remaining:

- mounted registrar batch-edit create-action path via
  [`backend/app/api/v1/endpoints/registrar_batch.py`](C:/final/backend/app/api/v1/endpoints/registrar_batch.py)
  and
  [`backend/app/services/batch_patient_service.py`](C:/final/backend/app/services/batch_patient_service.py)

Unmounted duplicates:

- `registrar_wizard_api_service.py`
- `registrar_integration_api_service.py`
- `registrar_batch_api_service.py`
- `queue_batch_service.py`
- legacy helper `_create_queue_entries()` in mounted `registrar_wizard.py`

## Verdict

`PARTIALLY_COMPLETE_WITH_ONE_REMAINING_PATH`

## Why Not `EFFECTIVELY_COMPLETE`

The registrar allocator track cannot yet be marked effectively complete because one mounted production-relevant path still:

- creates queue entries outside `QueueDomainService.allocate_ticket()`;
- has not gone through characterization;
- appears to rely on a stale `QueueService` import path.

If that `/registrar/batch` create-action branch did not exist, the remaining registrar allocator surfaces would be only duplicate/unmounted code and the track could be considered effectively complete.

## Why Not `NEEDS_ANOTHER_REGISTRAR_SLICE` In The Broad Sense

The track does not need another broad registrar campaign.

It needs exactly one narrow registrar follow-up slice focused on:

- mounted `/registrar/batch` create-action behavior;
- `BatchPatientService._create_entry()`;
- allocator ownership and runtime truth for that branch only.

So the remaining work is narrow, not a renewed broad registrar refactor.
