# Wave 2C Next Execution Unit After Registrar Follow-up

## Decision

`B) one more narrow registrar slice`

## Recommended Execution Unit

`Narrow runtime fix for mounted registrar batch create-action`

## Target Scope

Only:

- [`backend/app/api/v1/endpoints/registrar_batch.py`](C:/final/backend/app/api/v1/endpoints/registrar_batch.py)
  mounted `batch_update_patient_entries()` create-action path
- [`backend/app/services/batch_patient_service.py`](C:/final/backend/app/services/batch_patient_service.py)
  `_create_entry()`

## Why This Is The Right Next Step

- it is the only remaining production-relevant registrar allocator path outside the boundary architecture;
- it has now been characterized as live-but-broken;
- it is narrower than a broad registrar follow-up;
- moving to `qr_queue` now would leave one mounted registrar allocator path unresolved.

## Not Recommended As The Next Step

- `qr_queue` direct SQL characterization now:
  premature while one mounted registrar allocator branch remains unresolved
- `human review needed`:
  not necessary yet, because the next missing work is technical characterization, not contract ambiguity
- broad registrar refactor:
  disproportionate to the remaining scope

## Expected Next Slice Shape

A safe next slice should:

- repair or explicitly retire the mounted create-action branch;
- keep scope limited to `registrar_batch.py` and `batch_patient_service.py`;
- avoid any broader registrar, `qr_queue`, `OnlineDay`, or `force_majeure` work;
- preserve non-create batch-edit semantics.
