# W2C-MS-003 Plan

Date: 2026-03-07
Mode: Wave 2C Phase 1 continuation
Contract: `.ai-factory/contracts/w2c-ms-003.contract.json`

## Files

- `backend/app/api/v1/endpoints/queue_cabinet_management.py`
- `backend/app/repositories/queue_read_repository.py`
- `backend/app/services/queue_domain_service.py`
- `backend/tests/architecture/test_w2c_queue_boundaries.py`
- `backend/tests/unit/test_queue_domain_service.py`

## Handlers

- `GET /queues/cabinet-info`
- `GET /queues/{queue_id}/cabinet-info`

## Current DB Access Pattern

Current cabinet read handlers call `QueueCabinetManagementApiService`, which reads
through `QueueCabinetManagementApiRepository`. The flow is already read-only, but it
does not use the new queue-domain read boundary introduced in Phase 1.

## Target Wiring

`router -> QueueDomainService -> QueueReadRepository`

Write paths remain unchanged:

- `PUT /queues/{queue_id}/cabinet-info`
- `PUT /queues/cabinet-info/bulk`
- `POST /queues/sync-cabinet-info`
- `GET /queues/cabinet-statistics`

## Risk Analysis

Low.

Why it is safe:

- cabinet info is metadata-oriented
- selected handlers do not mutate queue state
- selected handlers do not depend on numbering, duplicate policy, QR windows, or visit lifecycle

## Runtime Invariants That Must Not Change

- `DailyQueue.specialist_id` continues to use runtime FK semantics (`doctors.id`)
- cabinet read response schema stays unchanged
- queue entry counts remain based on current `OnlineQueueEntry` rows
- no change to queue ordering, fairness, duplicate checks, or queue status semantics
