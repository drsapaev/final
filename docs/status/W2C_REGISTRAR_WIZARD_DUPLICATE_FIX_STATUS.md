# Wave 2C Registrar Wizard Duplicate Fix Status

Date: 2026-03-08
Status: `done`
Mode: behavior-correction, narrow mounted scope

## Files Changed

- `backend/app/services/morning_assignment.py`
- `backend/tests/characterization/test_registrar_wizard_queue_characterization.py`
- `backend/tests/unit/test_registrar_wizard_reuse_existing_entry.py`
- `docs/architecture/W2C_REGISTRAR_WIZARD_BEHAVIOR_CORRECTION.md`
- `docs/status/W2C_REGISTRAR_WIZARD_DUPLICATE_FIX_STATUS.md`
- `docs/status/W2C_REGISTRAR_WIZARD_CLASSIFICATION.md`
- `docs/status/W2C_REGISTRAR_WIZARD_NEXT_STEP_V3.md`

## Old Runtime Behavior

- same-day wizard reuse was queue-local but did not explicitly use canonical
  active statuses
- ambiguity inside the same queue-tag claim could fall through to unsafe reuse
  or unsafe creation paths

## Corrected Behavior

- wizard-family duplicate gate remains queue-tag-level
- canonical active statuses are now used:
  - `waiting`
  - `called`
  - `in_service`
  - `diagnostics`
- one compatible active row is reused
- different `queue_tag` claims still allow separate rows
- ambiguous same-claim ownership now results in safe no-allocation behavior in
  the mounted `/registrar/cart` flow

## Why Behavior Stayed Safe

- numbering still delegates to the same legacy allocator path
- `queue_time` for reused rows is preserved
- `queue_time` for new rows is still allocated the old way
- billing and visit creation were not refactored
- future-day flows still skip immediate queue allocation

## Test Commands

- `cd backend && pytest backend/tests/characterization/test_registrar_wizard_queue_characterization.py -q -c pytest.ini`
- `cd backend && pytest tests/unit/test_registrar_wizard_reuse_existing_entry.py -q`
- `cd backend && pytest tests/characterization -q -c pytest.ini`
- `cd backend && pytest tests/test_openapi_contract.py -q`
- `cd backend && pytest -q`

## Results

- wizard characterization: `9 passed`
- wizard reuse-entry unit tests: `4 passed`
- full characterization suite: `32 passed`
- OpenAPI contract: `10 passed`
- full backend suite: `734 passed, 3 skipped`

## Readiness Outcome

- claim ambiguity is no longer the primary blocker
- broader wizard-family is still not ready for boundary migration
- next safe step is a boundary-readiness recheck, not migration
