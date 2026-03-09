# Wave 2C Registrar Batch Create-Action Liveness

## Verdict

`LIVE_BUT_BROKEN`

## Verification Result

The mounted path is live:

- route exists and is mounted:
  `PATCH /api/v1/registrar/batch/patients/{patient_id}/entries/{date}`
- create-action requests enter
  [`BatchPatientService.batch_update()`](C:/final/backend/app/services/batch_patient_service.py)
  and dispatch to `_create_entry()`

The mounted path is broken:

- `_create_entry()` imports `QueueService` from
  [`backend/app/services/queue_service.py`](C:/final/backend/app/services/queue_service.py)
- that symbol is not exported there
- runtime result is an import failure before allocator execution

## Characterized Runtime Behavior

Mounted endpoint behavior:

- request reaches mounted create-action branch;
- branch returns HTTP `400`;
- endpoint detail is `One or more operations failed`;
- no new `OnlineQueueEntry` row is created.

Service-level behavior:

- `BatchPatientService.batch_update()` catches the per-entry exception;
- `updated_entries[0].error` contains:
  `cannot import name 'QueueService'`

Duplicate scenario behavior:

- even if a patient already has an active queue row, the create-action branch still fails before any duplicate-aware allocation step;
- existing rows remain untouched;
- no new number is issued.

## Why This Is Not `DEAD_OR_UNREACHABLE`

This is not dead code because:

- the route is mounted;
- the request reaches the branch in tests;
- the failure happens during runtime execution, not because the branch is unreachable.

## Why This Is Not `LIVE_AND_WORKING`

The branch never reaches successful allocation in current runtime because the import error happens first.
