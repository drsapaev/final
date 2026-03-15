# Wave 2C Registrar Batch Create-Action Fix Status

## Status

`done`

## Scope

Narrow runtime fix for the mounted `/registrar/batch` create-action branch only.

In scope:

- [`backend/app/services/batch_patient_service.py`](C:/final/backend/app/services/batch_patient_service.py)
- characterization and unit tests for this mounted path

Out of scope:

- broad registrar refactor
- allocator redesign
- `qr_queue`
- `OnlineDay`
- `force_majeure`

## Old Broken Behavior

- mounted runtime reached `BatchPatientService._create_entry()`
- `_create_entry()` attempted `from app.services.queue_service import QueueService`
- import failed
- endpoint returned `400`
- no queue row was created

## New Working Behavior

- `_create_entry()` now resolves patient/service/queue context locally
- create-action uses `QueueDomainService.allocate_ticket(allocation_mode="create_entry", ...)`
- mounted endpoint no longer fails on the stale import
- queue row is created through the supported boundary architecture

## Files Changed

- [`backend/app/services/batch_patient_service.py`](C:/final/backend/app/services/batch_patient_service.py)
- [`backend/tests/characterization/test_registrar_batch_create_action_characterization.py`](C:/final/backend/tests/characterization/test_registrar_batch_create_action_characterization.py)
- [`backend/tests/unit/test_registrar_batch_create_action_fix.py`](C:/final/backend/tests/unit/test_registrar_batch_create_action_fix.py)
- [`docs/status/W2C_REGISTRAR_BATCH_CREATE_FIX_PLAN.md`](C:/final/docs/status/W2C_REGISTRAR_BATCH_CREATE_FIX_PLAN.md)
- [`docs/architecture/W2C_REGISTRAR_BATCH_CREATE_ACTION_RUNTIME_FIX.md`](C:/final/docs/architecture/W2C_REGISTRAR_BATCH_CREATE_ACTION_RUNTIME_FIX.md)

## Observable Semantics Preserved

- mounted endpoint contract stayed intact
- `source="batch_update"` is preserved
- numbering still comes from the legacy allocator behind `QueueDomainService`
- `queue_time` still comes from the legacy allocator path
- duplicate behavior for this mounted micro-family remains characterization-based
  and unchanged by this fix

## Tests Run

- `pytest backend/tests/characterization/test_registrar_batch_create_action_characterization.py -q -c backend/pytest.ini`
- `cd backend && pytest tests/unit/test_registrar_batch_create_action_fix.py -q`
- `cd backend && pytest tests/characterization -q -c pytest.ini`
- `cd backend && pytest tests/test_openapi_contract.py -q`
- `cd backend && pytest -q`

## Results

- create-action characterization: `3 passed`
- create-action unit fix tests: `2 passed`
- full characterization suite: `35 passed`
- OpenAPI contract: `10 passed`
- full backend suite: `743 passed, 3 skipped`

## Registrar Track Impact

This slice removes the last known mounted broken registrar allocator path.

Result:

- registrar production allocator track is now effectively complete
- remaining registrar allocator debt is duplicate/unmounted cleanup, not a
  mounted runtime blocker
