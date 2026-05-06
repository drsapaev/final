# W2C-MS-006 Status

Date: 2026-03-07
Status: done
Contract: `.ai-factory/contracts/w2c-ms-006.contract.json`

## Files Changed

- `backend/app/repositories/queue_read_repository.py`
- `backend/app/repositories/queue_reorder_api_repository.py`
- `backend/app/services/queue_domain_service.py`
- `backend/app/services/queue_reorder_api_service.py`
- `backend/tests/unit/test_queue_domain_service.py`
- `backend/tests/unit/test_queue_reorder_api_service.py`
- `backend/tests/architecture/test_w2c_queue_boundaries.py`

## Architecture Change

Read-only queue snapshot/status flow now follows:

`queue_reorder router -> QueueReorderApiService -> QueueDomainService -> QueueReadRepository`

Write-oriented reorder methods remain on `QueueReorderApiRepository` and were not
changed semantically.

## Behavior Compatibility

- `get_queue_status()` still returns the same queue info shape
- `get_queue_status_by_specialist()` still returns the same queue info shape
- entry ordering for snapshot/status remains by queue number
- reorder write semantics were not changed

## Tests Run

- `cd backend && pytest tests/unit/test_queue_domain_service.py tests/unit/test_queue_reorder_api_service.py tests/architecture/test_w2c_queue_boundaries.py -q`
- `cd backend && pytest -q`
- `cd backend && pytest tests/test_openapi_contract.py -q`

## Results

- targeted tests: passed
- full backend suite: passed (`666 passed, 3 skipped`)
- openapi contract: passed (`10 passed`)

## Regressions

None detected.
