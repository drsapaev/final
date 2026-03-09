# Wave 2C Registrar Batch Create-Action Analysis

## Family Ownership

This path does **not** belong to the already migrated registrar batch-only family.

It is better understood as a separate registrar legacy micro-family attached to the mounted batch-edit endpoint:

- route family:
  `/registrar/batch/patients/{patient_id}/entries/{date}`
- purpose:
  UI row to API entry batch editing
- create branch:
  legacy queue row creation through `QueueService.add_to_queue(...)`

## Why It Is Separate From Batch-Only Family

The migrated registrar batch-only family:

- lives in [`backend/app/api/v1/endpoints/registrar_integration.py`](C:/final/backend/app/api/v1/endpoints/registrar_integration.py)
- groups services by specialist;
- reuses specialist-level active rows;
- already goes through `QueueDomainService.allocate_ticket()`

The mounted batch-edit create-action path instead:

- uses `specialty`/`service_code` style inputs;
- hardcodes `source="batch_update"`;
- has no local duplicate gate;
- has no current boundary usage;
- does not share the batch-only request/claim model.

## Runtime Classification

`legacy micro-family, mounted, currently broken`

## Track Implication

This branch still belongs to the broader registrar allocator track because:

- it is mounted;
- it can create queue rows in registrar-driven workflow;
- it is not dead duplicate code.

But it should be treated as its own narrow slice, not as part of:

- confirmation family;
- registrar batch-only family;
- wizard family.

## Safe Conclusion

Current safest conclusion:

- do not mark it dead;
- do not migrate it yet;
- do not fold it into another registrar family by assumption;
- treat it as a separate mounted legacy micro-family that needs a narrow runtime fix or explicit deprecation decision.
