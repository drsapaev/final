# Wave 2C Wizard Allocator Extraction Status

Date: 2026-03-08
Status: `done`
Mode: behavior-preserving decomposition

## Files Changed

- `backend/app/api/v1/endpoints/registrar_wizard.py`
- `backend/app/services/registrar_wizard_queue_assignment_service.py`
- `backend/tests/unit/test_wizard_allocator_extraction.py`
- `docs/status/W2C_WIZARD_ALLOCATOR_EXTRACTION_PLAN.md`
- `docs/architecture/W2C_WIZARD_ALLOCATOR_EXTRACTION.md`
- `docs/status/W2C_WIZARD_ALLOCATOR_EXTRACTION_STATUS.md`
- `docs/status/W2C_REGISTRAR_WIZARD_ALLOCATOR_SURFACE.md`
- `docs/status/W2C_REGISTRAR_WIZARD_BOUNDARY_READINESS_V2.md`
- `docs/status/W2C_NEXT_EXECUTION_UNIT_AFTER_WIZARD_EXTRACTION.md`

## Old Surface

Mounted `/registrar/cart` directly owned the same-day queue-assignment loop and
called `MorningAssignmentService` inline.

## New Surface

Mounted `/registrar/cart` now delegates same-day queue assignment to:

- `RegistrarWizardQueueAssignmentService.assign_same_day_queue_numbers(...)`

The extracted service still delegates to the same underlying
`MorningAssignmentService` logic.

## Why Behavior Did Not Drift

- no numbering algorithm change
- no `queue_time` change
- no fairness change
- no duplicate-policy change
- no billing or invoice behavior change
- same-day wizard characterization stayed green
- broader backend suite stayed green

## Test Commands

- `cd backend && pytest backend/tests/characterization/test_registrar_wizard_queue_characterization.py -q -c pytest.ini`
- `cd backend && pytest tests/unit/test_registrar_wizard_reuse_existing_entry.py tests/unit/test_wizard_allocator_extraction.py -q`
- `cd backend && pytest tests/characterization -q -c pytest.ini`
- `cd backend && pytest tests/test_openapi_contract.py -q`
- `cd backend && pytest -q`

## Results

- wizard characterization: `9 passed`
- wizard reuse + extraction unit tests: `6 passed`
- full characterization suite: `32 passed`
- OpenAPI contract: `10 passed`
- full backend suite: `736 passed, 3 skipped`

## Outcome

Wizard-family now has a narrower allocator seam.

It is closer to boundary migration, but the next correct step is still a
readiness recheck rather than immediate migration.
