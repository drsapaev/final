# W2D registrar_wizard_api_service cleanup

## What changed

Removed:

- `backend/app/services/registrar_wizard_api_service.py`

## Why this was safe

The file was a duplicate service-router mirror, not the mounted runtime owner.

The active runtime path already lives in:

- `backend/app/api/v1/endpoints/registrar_wizard.py`
- `backend/app/services/registrar_wizard_queue_assignment_service.py`
- `backend/app/services/visit_confirmation_service.py`
- `backend/app/services/morning_assignment.py`

## What did not change

This slice did not change:

- `/registrar-wizard` route registration
- cart creation behavior
- confirmation behavior
- queue assignment semantics
- allocator logic

## Practical effect

One more duplicate registrar-wizard artifact is removed without changing live
wizard behavior.

## Test-gate alignment

One stale service-boundary test still referenced the removed duplicate file.
That gate was updated to stop asserting on a module that no longer belongs to
the runtime or cleanup target set.
