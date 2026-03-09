# Wave 2C Wizard Boundary Migration Status

Date: 2026-03-09
Status: done
Mode: behaviour-preserving migration

## Files Changed

- `backend/app/services/registrar_wizard_queue_assignment_service.py`
- `backend/tests/unit/test_wizard_create_branch_extraction.py`
- `docs/status/W2C_WIZARD_BOUNDARY_MIGRATION_PLAN.md`
- `docs/architecture/W2C_WIZARD_BOUNDARY_MIGRATION.md`
- `docs/status/W2C_WIZARD_BOUNDARY_MIGRATION_STATUS.md`
- `docs/architecture/W2C_ALLOCATOR_COMPATIBILITY_LAYER.md`
- `docs/architecture/W2C_QUEUE_DOMAIN_SERVICE.md`
- `docs/architecture/W2C_ALLOCATOR_MIGRATION_STRATEGY.md`
- `docs/status/W2C_PHASE21_DEFERRED_CALLERS.md`
- `docs/status/W2C_NEXT_EXECUTION_UNIT_AFTER_WIZARD_MIGRATION.md`

## Old Path vs New Path

Old path:

- wizard-local handoff materialized queue creation through direct
  `queue_service.create_queue_entry(...)`

New path:

- wizard-local handoff materializes queue creation through
  `QueueDomainService.allocate_ticket(...)`
- the boundary still delegates to the same legacy allocator internally

## Behavior Preservation

- same `queue_tag` reuse unchanged
- different `queue_tag` fan-out unchanged
- numbering unchanged
- `queue_time` unchanged
- fairness unchanged
- source unchanged
- future-day behavior unchanged
- billing/invoice observed behavior unchanged

## Tests Run

- `pytest backend/tests/characterization/test_registrar_wizard_queue_characterization.py -q -c backend/pytest.ini`
- `cd backend && pytest tests/unit/test_registrar_wizard_reuse_existing_entry.py tests/unit/test_wizard_allocator_extraction.py tests/unit/test_wizard_create_branch_extraction.py tests/unit/test_queue_allocator_boundary.py -q`
- `cd backend && pytest tests/characterization -q -c pytest.ini`
- `cd backend && pytest tests/test_openapi_contract.py -q`
- `cd backend && pytest -q`

## Result

Mounted wizard-family now uses the queue-domain compatibility boundary for the
same-day create branch.
