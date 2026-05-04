# W2C-MS-001 Status

Date: 2026-03-07
Status: done
Contract: `.ai-factory/contracts/w2c-ms-001.contract.json`

## Files Changed

- `backend/app/services/queue_status.py`
- `backend/app/repositories/queue_position_api_repository.py`
- `backend/tests/unit/test_queue_status.py`
- `docs/architecture/W2C_STATUS_NORMALIZATION.md`

## Architecture Change

Queue read-status vocabulary is now centralized in `queue_status.py`.
`QueuePositionApiRepository.list_position_entries()` imports
`POSITION_VISIBLE_RAW_STATUSES` from that helper instead of duplicating a local
string list.

## Behavior Compatibility

- queue-position visible statuses remain exactly:
  - `waiting`
  - `called`
  - `in_service`
  - `diagnostics`
- no API response shape changed
- no persisted status values changed

## Tests Run

- `cd backend && pytest tests/unit/test_queue_status.py tests/unit/test_queue_position_api_service.py -q`
- `cd backend && pytest -q`
- `cd backend && pytest tests/test_openapi_contract.py -q`

## Results

- targeted tests: passed
- full backend suite: passed (`666 passed, 3 skipped`)
- openapi contract: passed (`10 passed`)

## Regressions

None detected.
