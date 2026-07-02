# W2C-MS-004 Plan

Date: 2026-03-07
Mode: Wave 2C Phase 1 continuation
Contract: `.ai-factory/contracts/w2c-ms-004.contract.json`

## Files

- `backend/app/api/v1/endpoints/services.py`
- `backend/app/repositories/queue_read_repository.py`
- `backend/app/services/queue_domain_service.py`
- `backend/tests/architecture/test_w2c_queue_boundaries.py`
- `backend/tests/unit/test_queue_domain_service.py`
- `backend/tests/unit/test_services_router_service_wiring.py`

## Handlers

- `GET /services/queue-groups`
- `GET /services/code-mappings`

## Current DB Access Pattern

Both handlers live in `services.py` and currently build payloads inline using static
SSOT mappings plus direct `db.query(Service)` enrichment.

## Target Wiring

`router -> QueueDomainService -> QueueReadRepository`

Not included in this slice:

- `GET /services/resolve`
- services catalog/category CRUD
- any queue mutation or runtime queue lifecycle endpoint

## Risk Analysis

Low to medium.

Queue taxonomy is domain-sensitive, so this slice preserves existing static mappings and
only moves payload construction behind the queue read boundary.

## Runtime Invariants That Must Not Change

- static `QUEUE_GROUPS` and `SPECIALTY_ALIASES` semantics
- DB enrichment behavior for active services
- response schemas of `queue-groups` and `code-mappings`
- no change to numbering, duplicate policy, fairness ordering, visit lifecycle, or QR restrictions
