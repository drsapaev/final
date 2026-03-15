# W2D queue_batch_service cleanup plan

Date: 2026-03-11
Mode: bounded cleanup

## Scope

Remove only:

- `backend/app/services/queue_batch_service.py`
- `backend/tests/unit/test_queue_batch_service.py`

## Why this candidate is in scope

The service file is already documented as `DEAD_OR_DUPLICATE` in the registrar
follow-up inventory.

Current review confirms:

- no live source imports remain under `backend/app`
- no backend test imports remain except its own unit test file
- mounted runtime already lives elsewhere

## What remains out of scope

- `backend/app/repositories/queue_batch_repository.py`
- mounted registrar batch runtime in `backend/app/api/v1/endpoints/registrar_batch.py`
- `BatchPatientService`
- any queue allocation behavior changes

`queue_batch_repository.py` is explicitly out of scope because it is still used
by characterization coverage.
