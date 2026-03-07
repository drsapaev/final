# Wave 2C Confirmation Reuse Fix Status

Date: 2026-03-07
Status: `done`
Mode: behaviour-correction, small diff

## Files Changed

- `backend/app/repositories/visit_confirmation_repository.py`
- `backend/app/services/visit_confirmation_service.py`
- `backend/app/api/v1/endpoints/registrar_wizard.py`
- `backend/tests/characterization/test_confirmation_split_flow_characterization.py`
- `backend/tests/unit/test_confirmation_reuse_existing_entry.py`
- `docs/architecture/W2C_CONFIRMATION_BEHAVIOR_CORRECTION.md`
- `docs/status/W2C_CONFIRMATION_REUSE_FIX_STATUS.md`
- `docs/status/W2C_CONFIRMATION_BOUNDARY_READINESS.md`
- `docs/status/W2C_CONFIRMATION_NEXT_EXECUTION_UNIT_V2.md`

## Old Behavior Corrected

Old behavior:

- same-day confirmation created a fresh `source="confirmation"` queue row even
  when an active row already existed in the same queue/day

New behavior:

- clear existing active row is reused
- no new ticket number is allocated in reuse case
- ambiguous ownership returns explicit `409`
- fresh row is still created through the legacy allocator only when no active
  row exists

## How Reuse Now Works

For each confirmation queue claim:

1. determine queue/day as before
2. search active rows using canonical statuses
3. resolve identity with `patient_id -> phone -> telegram_id`
4. if exactly one compatible row exists, reuse it
5. if none exists, create a new row as before
6. if more than one compatible row exists, return explicit conflict

## Tests Run

- `pytest backend/tests/characterization/test_confirmation_split_flow_characterization.py -q -c backend/pytest.ini`
- `pytest backend/tests/characterization/test_confirmation_split_flow_concurrency.py -q -c backend/pytest.ini`
- `cd backend && pytest tests/unit/test_confirmation_reuse_existing_entry.py tests/unit/test_visit_confirmation_service.py -q`
- `cd backend && pytest tests/characterization -q -c pytest.ini`
- `cd backend && pytest tests/test_openapi_contract.py -q`
- `cd backend && pytest -q`

## Results

- confirmation characterization: `6 passed`
- confirmation concurrency characterization: `2 passed`
- focused unit tests: `5 passed`
- full characterization suite: `15 passed`
- OpenAPI contract: `10 passed`
- full backend suite: `703 passed, 3 skipped`

## Guardrail Outcome

- numbering algorithm unchanged
- fairness ordering unchanged
- existing `queue_time` unchanged on reused rows
- no `OnlineDay` changes
- no `qr_queue` migration
- no broad registrar migration
