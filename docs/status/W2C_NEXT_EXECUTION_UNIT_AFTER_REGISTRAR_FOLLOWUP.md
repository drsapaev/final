# Wave 2C Next Execution Unit After Registrar Follow-up

## Decision

`B) one more narrow registrar slice`

## Recommended Execution Unit

`Registrar batch-edit create-action characterization`

## Target Scope

Only:

- [`backend/app/api/v1/endpoints/registrar_batch.py`](C:/final/backend/app/api/v1/endpoints/registrar_batch.py)
  mounted `batch_update_patient_entries()` create-action path
- [`backend/app/services/batch_patient_service.py`](C:/final/backend/app/services/batch_patient_service.py)
  `_create_entry()`

## Why This Is The Right Next Step

- it is the only remaining production-relevant registrar allocator path outside the boundary architecture;
- it is narrower than a broad registrar follow-up;
- it should be characterized before any migration or correction;
- it already shows concrete runtime drift (`QueueService` import mismatch), so moving to `qr_queue` now would leave one mounted registrar allocator path unresolved.

## Not Recommended As The Next Step

- `qr_queue` direct SQL characterization now:
  premature while one mounted registrar allocator branch remains unresolved
- `human review needed`:
  not necessary yet, because the next missing work is technical characterization, not contract ambiguity
- broad registrar refactor:
  disproportionate to the remaining scope

## Expected Next Slice Shape

A safe next slice should:

- be characterization-first;
- verify whether `/registrar/batch` create-action is actually exercised and how it behaves;
- add tests around `_create_entry()` and mounted create-action dispatch;
- determine whether the path needs a narrow runtime correction before any later boundary migration or can be retired as dead UI surface.
