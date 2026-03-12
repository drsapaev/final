# W2D registrar_integration_api_service cleanup

## What changed

Removed:

- `backend/app/services/registrar_integration_api_service.py`

## Why this was safe

The file was a duplicate service-router mirror, not the mounted runtime owner.

The active runtime path already lives in:

- `backend/app/api/v1/endpoints/registrar_integration.py`
- `backend/app/services/batch_patient_service.py`
- `backend/app/services/queue_domain_service.py`

## What did not change

This slice did not change:

- `/registrar/*` route registration
- queue batch behavior
- registrar allocator behavior
- queue-domain semantics

## Practical effect

One more duplicate registrar integration artifact is removed without changing
live registrar behavior.

## Test-gate alignment

One stale service-boundary test still referenced the removed duplicate file.
That gate was updated to stop asserting on a module that no longer belongs to
the runtime or cleanup target set.
