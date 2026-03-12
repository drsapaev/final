# Wave 2C QR Payload Compatibility Fix Status

Date: 2026-03-09
Status: done

## Files Changed

- `backend/app/services/qr_full_update_queue_assignment_service.py`
- `backend/app/services/queue_service.py`
- `backend/tests/characterization/test_qr_queue_direct_sql_characterization.py`
- `backend/tests/unit/test_qr_create_branch_extraction.py`
- `backend/tests/unit/test_qr_payload_compatibility.py`

## What Was Fixed

- QR-local handoff now exposes a boundary-compatible create-entry kwargs builder
- create-entry compatibility path now preserves:
  - `birth_year`
  - `address`
- QR handoff payload uses boundary-compatible field names for:
  - `services`
  - `service_codes`

## What Was Not Changed

- no mounted QR caller migration yet
- no numbering redesign
- no `queue_time` change
- no source-semantic change
- no duplicate-policy redesign

## Tests Run

- `pytest backend/tests/characterization/test_qr_queue_direct_sql_characterization.py -q -c backend/pytest.ini`
- `cd backend && pytest tests/unit/test_qr_create_branch_extraction.py tests/unit/test_qr_payload_compatibility.py -q`
- `cd backend && pytest tests/characterization -q -c pytest.ini`
- `cd backend && pytest tests/test_openapi_contract.py -q`
- `cd backend && pytest -q`

## Results

- QR characterization: passed
- QR extraction + compatibility unit tests: passed
- full characterization suite: passed
- OpenAPI contract: passed
- full backend suite: passed

## Readiness Outcome

The QR payload compatibility blocker is closed.

Current outcome:

- family is now ready for QR boundary migration
- migration itself remains a separate next slice
