# Wave 2C Registrar Batch Boundary Migration Status

Date: 2026-03-08
Status: `done`
Mode: behaviour-preserving migration

## Files Changed

- `backend/app/api/v1/endpoints/registrar_integration.py`
- `backend/tests/unit/test_registrar_batch_allocator_boundary.py`
- `docs/status/W2C_REGISTRAR_BATCH_BOUNDARY_MIGRATION_PLAN.md`
- `docs/architecture/W2C_REGISTRAR_BATCH_BOUNDARY_MIGRATION.md`
- `docs/status/W2C_REGISTRAR_BATCH_BOUNDARY_MIGRATION_STATUS.md`
- `docs/architecture/W2C_ALLOCATOR_COMPATIBILITY_LAYER.md`
- `docs/architecture/W2C_QUEUE_DOMAIN_SERVICE.md`
- `docs/architecture/W2C_ALLOCATOR_MIGRATION_STRATEGY.md`
- `docs/status/W2C_PHASE21_DEFERRED_CALLERS.md`
- `docs/status/W2C_NEXT_EXECUTION_UNIT_AFTER_BATCH.md`

## Old Path

- mounted batch-only create branch called `queue_service.create_queue_entry(...)`
  directly

## New Path

- mounted batch-only create branch now calls
  `QueueDomainService.allocate_ticket(allocation_mode="create_entry", ...)`
- `QueueDomainService` still delegates to the legacy allocator internally

## Why Behaviour Stayed Stable

- reuse-existing-entry branch was not moved
- ambiguity `409` branch was not moved
- only create branch changed caller path
- numbering and `queue_time` behavior stayed inside the same legacy allocator

## Test Commands

- `cd backend && pytest tests/characterization/test_registrar_batch_allocator_characterization.py -q -c pytest.ini`
- `cd backend && pytest tests/characterization/test_registrar_batch_allocator_concurrency.py -q -c pytest.ini`
- `cd backend && pytest tests/unit/test_registrar_batch_allocator_boundary.py -q`
- `cd backend && pytest tests/unit/test_registrar_batch_reuse_existing_entry.py tests/unit/test_queue_allocator_boundary.py -q`
- `cd backend && pytest tests/characterization -q -c pytest.ini`
- `cd backend && pytest tests/test_openapi_contract.py -q`
- `cd backend && pytest -q`

## Results

- registrar batch characterization: `6 passed`
- registrar batch concurrency characterization: `2 passed`
- registrar batch boundary unit tests: `3 passed`
- registrar batch reuse tests + queue boundary tests: `9 passed`
- full characterization suite: `23 passed`
- OpenAPI contract: `10 passed`
- full backend suite: `721 passed, 3 skipped`

## Deferred After This Slice

- broader registrar wizard characterization
- QR direct SQL family
- force-majeure family
- `OnlineDay` legacy isolation
