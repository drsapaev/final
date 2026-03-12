# W2D queue_batch_service cleanup

## What changed

Removed:

- `backend/app/services/queue_batch_service.py`
- `backend/tests/unit/test_queue_batch_service.py`

## Why this was safe

`queue_batch_service.py` no longer had live source imports in the backend app,
and its only remaining test dependency was the matching unit test file.

The active mounted registrar-batch runtime already lives in:

- `backend/app/api/v1/endpoints/registrar_batch.py`
- `backend/app/services/batch_patient_service.py`

## What did not change

This slice did not change:

- `/registrar/batch` route registration
- patient batch update behavior
- queue allocation behavior
- duplicate/reuse behavior
- characterization coverage that still relies on `QueueBatchRepository`

## Practical effect

One more duplicate service-side residue is removed while keeping the live
registrar-batch path intact.
