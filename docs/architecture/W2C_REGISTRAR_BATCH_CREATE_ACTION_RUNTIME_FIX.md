# Wave 2C Registrar Batch Create-Action Runtime Fix

## Scope

This slice fixes only the mounted `/registrar/batch` create-action runtime path:

- endpoint:
  [`backend/app/api/v1/endpoints/registrar_batch.py`](C:/final/backend/app/api/v1/endpoints/registrar_batch.py)
- service:
  [`backend/app/services/batch_patient_service.py`](C:/final/backend/app/services/batch_patient_service.py)

Out of scope:

- broader registrar refactor
- `qr_queue` direct SQL family
- `OnlineDay` legacy family
- `force_majeure` allocator family
- numbering redesign
- duplicate-policy redesign outside this mounted path

## Old Broken Behavior

Mounted runtime used:

1. `PATCH /api/v1/registrar/batch/patients/{patient_id}/entries/{date}`
2. `BatchPatientService.batch_update()`
3. `BatchPatientService._create_entry()`
4. `from app.services.queue_service import QueueService`
5. `QueueService(self.db).add_to_queue(...)`

That import no longer existed, so the mounted create-action branch failed before
queue allocation and the endpoint returned `400`.

## New Working Path

`BatchPatientService._create_entry()` now:

1. resolves patient/service/queue_tag for this mounted create-action only
2. resolves or creates the target `DailyQueue`
3. calls:
   `QueueDomainService.allocate_ticket(allocation_mode="create_entry", ...)`

The new call still delegates to the legacy allocator internally, so this is a
runtime-fix and caller-path normalization, not an allocator redesign.

## Why The Fix Is Narrow

- no changes to mounted endpoint shape
- no changes to numbering algorithm
- no changes to `queue_time` ownership
- no changes to fairness ordering
- no changes to `qr_queue`, `OnlineDay`, `force_majeure`, or migrated registrar families
- no broad `batch_patient_service` rewrite beyond this broken create-action branch

## Observable Behavior After Fix

- mounted create-action no longer fails on `ImportError`
- queue row creation succeeds through the supported queue boundary path
- `source="batch_update"` is preserved
- numbering is still produced by the legacy allocator behind
  `QueueDomainService.allocate_ticket()`
- duplicate behavior for this micro-family stays narrow and characterization-based:
  an existing `diagnostics` row does not get collapsed here; a new `batch_update`
  row receives the next number

## What This Means For Queue Architecture

This mounted registrar path is now covered by the queue compatibility boundary.
It no longer bypasses supported allocation architecture through a stale
`QueueService` import.

Remaining registrar allocator debt after this slice is limited to duplicate or
unmounted code paths, not active mounted runtime flow.
