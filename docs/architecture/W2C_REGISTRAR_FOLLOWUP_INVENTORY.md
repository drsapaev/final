# Wave 2C Registrar Follow-up Inventory

## Scope

This pass inventories only registrar-related backend paths that can still:

- create queue entries;
- invoke queue numbering;
- bypass `QueueDomainService.allocate_ticket()`;
- alter duplicate/reuse behavior for registrar-owned queue joins;
- or change visit-to-queue linkage during registrar-driven flows.

Pure read endpoints, payment-only actions, and queue status updates without allocation are out of scope for this document.

`Production relevant` below means the path is mounted in [`backend/app/api/v1/api.py`](C:/final/backend/app/api/v1/api.py) through an endpoint router and is reachable in the current API surface. Unmounted `*_api_service.py` routers are treated as duplicate runtime surfaces, not production truth.

## Inventory

| Path | Function / flow | Mounted | Production relevant | Queue allocation | Direct legacy allocator usage | Already covered by migrated family | Recommended disposition | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `backend/app/api/v1/endpoints/registrar_integration.py` | `create_queue_entries_batch()` | Yes | Yes | Yes | No | Yes | `ALREADY_COVERED_BY_BOUNDARY` | Batch-only mounted family already migrated to `QueueDomainService.allocate_ticket()` |
| `backend/app/api/v1/endpoints/registrar_wizard.py` | `create_cart_appointments()` same-day path | Yes | Yes | Yes | No | Yes | `ALREADY_COVERED_BY_BOUNDARY` | Mounted wizard same-day path delegates to `RegistrarWizardQueueAssignmentService` and then to boundary |
| `backend/app/api/v1/endpoints/registrar_wizard.py` | `confirm_visit_by_registrar()` -> `_assign_queue_numbers_on_confirmation()` | Yes | Yes | Yes | No | Yes | `ALREADY_COVERED_BY_BOUNDARY` | Registrar confirmation bridge now reuses the migrated confirmation family |
| `backend/app/services/registrar_wizard_queue_assignment_service.py` | `assign_same_day_queue_numbers()` / `_allocate_create_branch_handoff()` | Indirect helper | Yes (via mounted wizard flow) | Yes | No | Yes | `ALREADY_COVERED_BY_BOUNDARY` | Wizard-local seam materializes create branch through `QueueDomainService.allocate_ticket()` |
| `backend/app/api/v1/endpoints/registrar_batch.py` | `batch_update_patient_entries()` with `EntryAction(action="create")` | Yes | Yes | Yes | Yes (indirect) | No | `NEEDS_SEPARATE_CHARACTERIZATION` | Mounted registrar batch-edit surface still reaches legacy-style allocation through `BatchPatientService._create_entry()` |
| `backend/app/services/batch_patient_service.py` | `_create_entry()` | Indirect helper | Yes (via mounted registrar batch route) | Yes | Yes | No | `NEEDS_SEPARATE_CHARACTERIZATION` | Imports `QueueService` and calls `add_to_queue()`; this is outside already migrated registrar families |
| `backend/app/api/v1/endpoints/registrar_wizard.py` | `_create_queue_entries()` | Helper only | No | Yes | Yes | No | `DEAD_OR_DUPLICATE` | Legacy helper remains in mounted file but is not referenced by current mounted wizard flow |
| `backend/app/services/registrar_wizard_api_service.py` | `_create_queue_entries()`, cart queue assignment, confirmation queue creation | No | No | Yes | Yes | No | `DEAD_OR_DUPLICATE` | Duplicate service-router surface with manual/legacy allocation; not mounted in `api_router` |
| `backend/app/services/registrar_integration_api_service.py` | `create_queue_entries_batch()` | No | No | Yes | Yes (via `QueueBatchService`) | No | `DEAD_OR_DUPLICATE` | Duplicate service-router surface; mounted endpoint version already migrated separately |
| `backend/app/services/queue_batch_service.py` | `create_entries()` | Helper only | No (current runtime) | Yes | Yes | No | `DEAD_OR_DUPLICATE` | Current callers are only duplicate/unmounted service-router code |
| `backend/app/services/registrar_batch_api_service.py` | `batch_update_patient_entries()` | No | No | Yes (via `BatchPatientService`) | Yes (indirect) | No | `DEAD_OR_DUPLICATE` | Duplicate service-router mirror of mounted `/registrar/batch` path |

## Inventory Conclusion

After excluding already migrated families and unmounted duplicates, one mounted registrar-related allocator path still remains outside the boundary architecture:

- [`backend/app/api/v1/endpoints/registrar_batch.py`](C:/final/backend/app/api/v1/endpoints/registrar_batch.py)
  `batch_update_patient_entries()` create-action path
- via [`backend/app/services/batch_patient_service.py`](C:/final/backend/app/services/batch_patient_service.py)
  `_create_entry()`

That path is the only remaining production-relevant registrar allocator surface discovered in this pass.
