# Wave 2C Registrar Batch Create-Action Fix Plan

## Old Broken Path

Mounted flow:

1. `PATCH /api/v1/registrar/batch/patients/{patient_id}/entries/{date}`
2. `BatchPatientService.batch_update()`
3. `BatchPatientService._create_entry()`
4. `from app.services.queue_service import QueueService`
5. `QueueService(self.db).add_to_queue(...)`

Current runtime breaks at step 4 because `QueueService` is not exported from
`backend/app/services/queue_service.py`.

## Chosen Safe Replacement

Replace the broken import/call with:

1. local queue-resolution helper inside `BatchPatientService`
2. `QueueDomainService.allocate_ticket(allocation_mode="create_entry", ...)`

The boundary still delegates to the legacy queue allocator internally, so this
fix restores a supported queue-row creation path without redesigning numbering.

## Why This Is Behavior-Safe

- scope stays inside the mounted `/registrar/batch` create-action branch;
- no allocator redesign is introduced;
- numbering still comes from legacy `queue_service.create_queue_entry(...)`;
- `queue_time` still comes from the legacy allocator path;
- response contract remains the same endpoint/response model;
- already migrated confirmation / registrar batch-only / wizard families are
  not touched.

## What This Slice Will Not Change

- no `qr_queue` direct SQL migration
- no `OnlineDay` legacy changes
- no `force_majeure` changes
- no broader registrar refactor
- no duplicate-policy redesign outside this mounted create-action path

## Replacement Constraints

- resolve a target `DailyQueue` only for this path
- preserve `source="batch_update"`
- keep transaction ownership inside `BatchPatientService.batch_update()`
- document any remaining ambiguity explicitly instead of widening scope
