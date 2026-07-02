# W2C-MS-006 Plan

Date: 2026-03-07
Mode: Wave 2C Phase 1
Contract: `.ai-factory/contracts/w2c-ms-006.contract.json`

## Files

- `backend/app/repositories/queue_read_repository.py`
- `backend/app/repositories/queue_reorder_api_repository.py`
- `backend/app/services/queue_domain_service.py`
- `backend/app/services/queue_reorder_api_service.py`
- `backend/tests/architecture/test_w2c_queue_boundaries.py`
- `backend/tests/unit/test_queue_domain_service.py`
- `backend/tests/unit/test_queue_reorder_api_service.py`

## Endpoints / Functions

- `GET /queue-reorder/status/by-specialist/`
- `GET /queue-reorder/status/{queue_id}`
- `QueueReorderApiService.get_queue_status_by_specialist`
- `QueueReorderApiService.get_queue_status`

## Current Anti-Pattern

Queue snapshot/status reads live in the reorder-oriented API service and reuse the
same repository that owns reorder write persistence, so there is no explicit queue
domain read boundary.

## Target Architecture

- `router -> QueueReorderApiService -> QueueDomainService -> QueueReadRepository`
- reorder write handlers remain on `QueueReorderApiRepository`
- queue status endpoint behavior stays unchanged

## Expected Wiring

- `QueueReorderApiService` delegates only the read-only snapshot methods to `QueueDomainService`
- `QueueDomainService` uses `QueueReadRepository`
- `QueueReorderApiRepository` remains the write-oriented repository for reorder mutations

## Risk Level

Low to medium

## Protected Zone Check

Queue domain is a protected area, but this slice stays read-only and explicitly avoids
mutation, numbering, duplicate, and visit-link semantics.
