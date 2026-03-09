# Wave 2C Registrar Direct Allocator Remains

## Verdict

Registrar-related direct allocator usage still remains in one production-relevant mounted path.

## Production-Relevant Remaining Path

### 1. Mounted registrar batch edit/create flow

- Endpoint:
  [`backend/app/api/v1/endpoints/registrar_batch.py`](C:/final/backend/app/api/v1/endpoints/registrar_batch.py)
  `batch_update_patient_entries()`
- Helper:
  [`backend/app/services/batch_patient_service.py`](C:/final/backend/app/services/batch_patient_service.py)
  `_create_entry()`

Current allocation path:

1. mounted `/registrar/batch/patients/{patient_id}/entries/{date}` accepts a batch update;
2. `BatchPatientService.batch_update()` dispatches `EntryAction(action="create")`;
3. `_create_entry()` performs:
   `from app.services.queue_service import QueueService`
4. `_create_entry()` then calls:
   `QueueService(self.db).add_to_queue(...)`

Why this still counts as direct legacy allocator usage:

- it does not use `QueueDomainService.allocate_ticket()`;
- it does not go through any registrar-specific migrated seam;
- it targets a legacy-style queue service API rather than the new compatibility boundary.

## Why This Path Was Not Covered Earlier

Previous registrar slices covered different mounted families:

- confirmation bridge in `registrar_wizard.py`;
- batch-only create path in `registrar_integration.py`;
- wizard same-day cart path in `registrar_wizard.py`.

The `/registrar/batch` create-action path belongs to a separate batch-edit surface (`UI Row ↔ API Entry`) and was therefore outside those slices.

## Risk Assessment

Risk level: `MEDIUM-HIGH`

Why:

- the path is mounted and production-relevant;
- it bypasses the queue boundary architecture;
- it is not characterized yet;
- static inspection shows a concrete runtime drift signal:
  [`backend/app/services/batch_patient_service.py`](C:/final/backend/app/services/batch_patient_service.py)
  imports `QueueService`, but [`backend/app/services/queue_service.py`](C:/final/backend/app/services/queue_service.py) exports `QueueBusinessService` and `queue_service`, not `QueueService`.

## Verified Import Drift

This pass verified the import directly in the backend runtime environment:

```text
ImportError: cannot import name 'QueueService' from 'app.services.queue_service'
```

That means the remaining mounted registrar allocator path is not only outside the boundary, but also likely stale or broken when the create-action branch is exercised.

## Non-Production Direct Allocator Remains

The following registrar-related direct allocator paths still exist, but are not current production entry points:

- [`backend/app/api/v1/endpoints/registrar_wizard.py`](C:/final/backend/app/api/v1/endpoints/registrar_wizard.py)
  `_create_queue_entries()`
- [`backend/app/services/registrar_wizard_api_service.py`](C:/final/backend/app/services/registrar_wizard_api_service.py)
- [`backend/app/services/registrar_integration_api_service.py`](C:/final/backend/app/services/registrar_integration_api_service.py)
- [`backend/app/services/queue_batch_service.py`](C:/final/backend/app/services/queue_batch_service.py)
- [`backend/app/services/registrar_batch_api_service.py`](C:/final/backend/app/services/registrar_batch_api_service.py)

These should be treated as duplicate/unmounted cleanup debt, not as current registrar migration blockers.
