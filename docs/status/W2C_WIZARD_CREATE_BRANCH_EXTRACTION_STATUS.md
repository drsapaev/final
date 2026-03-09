# Wave 2C Wizard Create-Branch Extraction Status

Date: 2026-03-09
Status: done
Mode: behaviour-preserving extraction

## Files Changed

- `backend/app/services/morning_assignment.py`
- `backend/app/services/registrar_wizard_queue_assignment_service.py`
- `backend/tests/unit/test_wizard_allocator_extraction.py`
- `backend/tests/unit/test_wizard_create_branch_extraction.py`
- `docs/status/W2C_WIZARD_CREATE_BRANCH_EXTRACTION_PLAN.md`
- `docs/architecture/W2C_WIZARD_CREATE_BRANCH_EXTRACTION.md`
- `docs/status/W2C_WIZARD_ALLOCATOR_SURFACE.md`
- `docs/status/W2C_WIZARD_BOUNDARY_READINESS_V3.md`
- `docs/status/W2C_NEXT_EXECUTION_UNIT_AFTER_WIZARD_CREATE_BRANCH.md`

## Corrected Hidden Surface

Old hidden handoff:

- mounted wizard same-day flow reached
  `MorningAssignmentService._assign_single_queue(...)`
- shared morning-assignment code both prepared and executed the create branch

New explicit seam:

- `MorningAssignmentService.prepare_wizard_queue_assignment(...)` now returns
  either reuse payload or `MorningAssignmentCreateBranchHandoff`
- `RegistrarWizardQueueAssignmentService` now materializes the create branch
  explicitly in wizard-local code

## Behavior Preservation Notes

- numbering still comes from legacy `queue_service.create_queue_entry(...)`
- queue-tag-level claim model is unchanged
- same `queue_tag` reuse is unchanged
- different `queue_tag` rows are still allowed
- `queue_time` and fairness ordering are unchanged
- billing/invoice observed behavior is untouched

## Tests Run

- `pytest backend/tests/characterization/test_registrar_wizard_queue_characterization.py -q -c backend/pytest.ini`
- `pytest backend/tests/unit/test_registrar_wizard_reuse_existing_entry.py backend/tests/unit/test_wizard_allocator_extraction.py backend/tests/unit/test_wizard_create_branch_extraction.py -q`
- `cd backend && pytest tests/characterization -q -c pytest.ini`
- `cd backend && pytest tests/test_openapi_contract.py -q`
- `cd backend && pytest -q`

## Results

- wizard characterization: `9 passed`
- wizard reuse/extraction unit tests: `7 passed`
- full characterization suite: `32 passed`
- OpenAPI contract: `10 passed`
- full backend suite: `737 passed, 3 skipped`

## Outcome

The create-branch blocker was extracted successfully.

Wizard-family is now closer to boundary migration, but this slice does not
declare it migration-ready by itself. The next step is a narrow readiness
recheck on the extracted seam.
