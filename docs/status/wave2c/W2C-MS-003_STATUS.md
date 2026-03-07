# W2C-MS-003 Status

Date: 2026-03-07
Status: done
Contract: `.ai-factory/contracts/w2c-ms-003.contract.json`

## Files Changed

- `backend/app/api/v1/endpoints/queue_cabinet_management.py`
- `backend/app/repositories/queue_read_repository.py`
- `backend/app/services/queue_domain_service.py`
- `backend/tests/architecture/test_w2c_queue_boundaries.py`
- `backend/tests/unit/test_queue_domain_service.py`

## Architecture Change

Selected read-only cabinet handlers now use:

`router -> QueueDomainService -> QueueReadRepository`

Covered handlers:

- `GET /queues/cabinet-info`
- `GET /queues/{queue_id}/cabinet-info`

Not changed:

- cabinet write handlers
- cabinet sync handler
- cabinet statistics handler

## Runtime Behavior Notes

- response schemas remained unchanged
- `DailyQueue.specialist_id` continues to follow runtime `doctors.id` semantics
- queue entry counts still come from current `OnlineQueueEntry` rows
- no change to numbering, duplicate policy, fairness ordering, QR restrictions, or visit lifecycle

## Tests Run

- `cd backend && pytest tests/unit/test_queue_domain_service.py tests/unit/test_queue_cabinet_management_api_service.py tests/architecture/test_w2c_queue_boundaries.py -q`
- `cd backend && pytest tests/unit/test_service_repository_boundary.py -q`
- `cd backend && pytest -q`
- `cd backend && pytest tests/test_openapi_contract.py -q`

## Results

- targeted tests: passed
- service boundary tests: passed
- full backend suite: passed (`669 passed, 3 skipped`)
- openapi contract: passed (`10 passed`)

## Regressions

None detected.
