# W2D registrar_batch_api_service cleanup

## What changed

Removed:

- `backend/app/services/registrar_batch_api_service.py`

## Why this was safe

The file was a duplicate service-router mirror, not the mounted runtime owner.

The active runtime path already lives in:

- `backend/app/api/v1/endpoints/registrar_batch.py`
- `backend/app/services/batch_patient_service.py`

## What did not change

This slice did not change:

- `/registrar/batch` route registration
- patient batch update behavior
- batch cancellation behavior
- allocator logic
- registrar authorization rules

## Practical effect

One more duplicate registrar artifact is removed without changing live
registrar-batch behavior.
