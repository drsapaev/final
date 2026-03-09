# Wave 2C Registrar Follow-up Classification

## Category Map

### A) `ALREADY_COVERED_BY_BOUNDARY`

- [`backend/app/api/v1/endpoints/registrar_integration.py`](C:/final/backend/app/api/v1/endpoints/registrar_integration.py)
  `create_queue_entries_batch()`
- [`backend/app/api/v1/endpoints/registrar_wizard.py`](C:/final/backend/app/api/v1/endpoints/registrar_wizard.py)
  `create_cart_appointments()` same-day queue path
- [`backend/app/api/v1/endpoints/registrar_wizard.py`](C:/final/backend/app/api/v1/endpoints/registrar_wizard.py)
  `confirm_visit_by_registrar()` bridge
- [`backend/app/services/registrar_wizard_queue_assignment_service.py`](C:/final/backend/app/services/registrar_wizard_queue_assignment_service.py)
  wizard queue-assignment seam

Reason:

- these are mounted or production-serving seams;
- their allocator calls already pass through `QueueDomainService.allocate_ticket()`;
- prior characterization/correction slices already stabilized their duplicate and claim semantics.

### B) `DEAD_OR_DUPLICATE`

- [`backend/app/api/v1/endpoints/registrar_wizard.py`](C:/final/backend/app/api/v1/endpoints/registrar_wizard.py)
  `_create_queue_entries()`
- [`backend/app/services/registrar_wizard_api_service.py`](C:/final/backend/app/services/registrar_wizard_api_service.py)
  duplicate wizard router/service surface
- [`backend/app/services/registrar_integration_api_service.py`](C:/final/backend/app/services/registrar_integration_api_service.py)
  duplicate registrar integration router/service surface
- [`backend/app/services/queue_batch_service.py`](C:/final/backend/app/services/queue_batch_service.py)
  helper reachable only from duplicate/unmounted service-router code
- [`backend/app/services/registrar_batch_api_service.py`](C:/final/backend/app/services/registrar_batch_api_service.py)
  duplicate registrar batch router/service surface

Reason:

- not mounted in [`backend/app/api/v1/api.py`](C:/final/backend/app/api/v1/api.py);
- not part of current endpoint router truth;
- some still contain stale direct allocator logic, but they are not current production entry points.

### C) `NEEDS_SEPARATE_CHARACTERIZATION`

- [`backend/app/api/v1/endpoints/registrar_batch.py`](C:/final/backend/app/api/v1/endpoints/registrar_batch.py)
  `batch_update_patient_entries()` with `EntryAction(action="create")`
- [`backend/app/services/batch_patient_service.py`](C:/final/backend/app/services/batch_patient_service.py)
  `_create_entry()`

Reason:

- mounted and production-relevant;
- not covered by confirmation, registrar batch-only, or wizard-family migration slices;
- still bypass the boundary architecture;
- show runtime drift risk around legacy allocator import/use.

### D) `DEFER_SAFE`

None identified in this pass.

Rationale:

- every remaining registrar-related allocator path was either already migrated, obviously duplicate/unmounted, or the single mounted leftover requiring its own characterization.

### E) `LEGACY_LATE_TRACK`

None inside registrar-owned runtime scope.

Rationale:

- `qr_queue`, `OnlineDay`, and `force_majeure` remain separate allocator families, but they are outside registrar follow-up scope and should not be merged into registrar completeness accounting.
