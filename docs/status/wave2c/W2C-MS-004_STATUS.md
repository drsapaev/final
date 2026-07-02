# W2C-MS-004 Status

Date: 2026-03-07
Status: `done`
Mode: Wave 2C Phase 1 continuation
Contract: `.ai-factory/contracts/w2c-ms-004.contract.json`

## Files Changed

- `backend/app/api/v1/endpoints/services.py`
- `backend/app/repositories/queue_read_repository.py`
- `backend/app/services/queue_domain_service.py`
- `backend/tests/architecture/test_w2c_queue_boundaries.py`
- `backend/tests/unit/test_queue_domain_service.py`
- `backend/tests/unit/test_services_router_service_wiring.py`
- `docs/architecture/W2C_ONLINE_QUEUE_DOC_COMPLIANCE.md`
- `docs/architecture/W2C_QUEUE_DISCOVERY.md`
- `docs/architecture/W2C_QUEUE_DOMAIN_SERVICE.md`
- `docs/architecture/W2C_QUEUE_REPOSITORIES.md`
- `docs/status/W2C_SAFE_SLICES.md`
- `docs/status/W2C_PHASE1_EXECUTION_SUMMARY.md`

## Scope Executed

Completed only the narrowed read-only queue metadata slice:

- `GET /services/queue-groups`
- `GET /services/code-mappings`

Out of scope and left unchanged:

- `GET /services/resolve`
- service catalog/category CRUD
- queue numbering
- duplicate policy
- QR window logic
- visit-linked queue mutation flows

## Architecture Change

Read path now follows:

`router -> QueueDomainService -> QueueReadRepository`

Implemented pieces:

- `QueueReadRepository.list_active_services()`
- `QueueDomainService.get_queue_groups_payload()`
- `QueueDomainService.get_service_code_mappings_payload()`
- router delegation from `services.py` to the queue read boundary

## Runtime Compatibility Notes

- static `QUEUE_GROUPS` and `SPECIALTY_ALIASES` remain the source for taxonomy
- DB enrichment still uses active services only
- enrichment remains best-effort and falls back to static mappings on read failure
- response schemas were preserved

## Issue Found During Execution

`GET /services/code-mappings` was shadowed by `GET /services/{service_id}` and returned
`422` because the static route was declared below the dynamic route.

Applied fix:

- moved `/services/code-mappings` above `/{service_id}`

Why this stayed in scope:

- it is a read-only route-ordering fix inside the selected slice
- it does not change queue mutation semantics
- it does not change response shape
- it was required to make the selected static endpoint reachable

`GET /services/resolve` was still left outside this slice.

## Tests Run

- `cd backend && pytest tests/unit/test_queue_domain_service.py tests/unit/test_services_router_service_wiring.py tests/architecture/test_w2c_queue_boundaries.py tests/unit/test_service_repository_boundary.py -q`
- `cd backend && pytest -q`
- `cd backend && pytest tests/test_openapi_contract.py -q`

## Test Results

- targeted tests: `78 passed`
- full backend suite: `676 passed, 3 skipped`
- OpenAPI contract suite: `10 passed`

## Regressions

None remaining after the route-order fix.
