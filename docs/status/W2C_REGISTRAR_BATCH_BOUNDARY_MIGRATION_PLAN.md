# Wave 2C Registrar Batch Boundary Migration Plan

Date: 2026-03-08
Mode: behaviour-preserving migration
Scope: mounted registrar batch-only family

## Files In Scope

- `backend/app/api/v1/endpoints/registrar_integration.py`
- `backend/tests/characterization/test_registrar_batch_allocator_characterization.py`
- `backend/tests/characterization/test_registrar_batch_allocator_concurrency.py`
- `backend/tests/unit/test_registrar_batch_reuse_existing_entry.py`
- `backend/tests/unit/test_registrar_batch_allocator_boundary.py`
- `docs/architecture/W2C_REGISTRAR_BATCH_BOUNDARY_MIGRATION.md`
- `docs/status/W2C_REGISTRAR_BATCH_BOUNDARY_MIGRATION_STATUS.md`
- `docs/architecture/W2C_ALLOCATOR_COMPATIBILITY_LAYER.md`
- `docs/architecture/W2C_QUEUE_DOMAIN_SERVICE.md`
- `docs/architecture/W2C_ALLOCATOR_MIGRATION_STRATEGY.md`
- `docs/status/W2C_PHASE21_DEFERRED_CALLERS.md`
- `docs/status/W2C_NEXT_EXECUTION_UNIT_AFTER_BATCH.md`

## Why This Is Safe

- contract clarification is complete
- mounted batch duplicate-gate behavior is already corrected
- numbering stays inside legacy allocator
- create branch can switch caller path without redesigning allocator internals
- reuse and ambiguity logic remain in the mounted batch path

## Behaviour-Preservation Rules

- reuse-existing-entry logic stays unchanged
- `409` ambiguity handling stays unchanged
- if no active row exists, only the caller path changes
- numbering algorithm stays legacy
- `queue_time` and fairness stay unchanged
- no billing/payment logic is moved

## Explicitly Out Of Scope

- broader registrar wizard orchestration
- `queue_batch_service.py` as runtime owner
- QR allocator families
- `OnlineDay`
- force-majeure
- legacy count-based registrar paths
- non-batch registrar write flows
