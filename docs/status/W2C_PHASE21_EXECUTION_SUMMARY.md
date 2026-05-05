# Wave 2C Phase 2.1 Execution Summary

Date: 2026-03-07
Mode: behavior-preserving execution

## Completed Caller Migrations

- `backend/app/api/v1/endpoints/online_queue_new.py::join_queue()`
- `backend/app/services/qr_queue_service.py::complete_join_session()`
- `backend/app/services/qr_queue_service.py::complete_join_session_multiple()`

## What Changed

- selected callers now invoke `QueueDomainService.allocate_ticket()`
- the boundary still delegates to legacy `queue_service` allocator logic
- response shapes, numbering, duplicate behavior, and queue-time semantics were preserved

## Evidence

- targeted unit tests prove callers now use the boundary
- integration tests prove `/api/v1/online-queue/join` behavior remains unchanged
- existing QR join integration and allocator characterization tests remain green

## Tests Run

- `cd backend && pytest tests/unit/test_online_queue_new_allocator_boundary.py tests/unit/test_qr_queue_service_allocator_boundary.py tests/integration/test_online_queue_new_join.py tests/integration/test_qr_queue_join.py tests/characterization/test_queue_allocator_characterization.py -q`
- `cd backend && pytest tests/unit/test_queue_allocator_boundary.py -q`
- `cd backend && pytest -q`
- `cd backend && pytest tests/test_openapi_contract.py -q`
- `pytest backend/tests/characterization -q -c backend/pytest.ini`

## Result

- targeted migration tests:
  - `14 passed`
  - boundary-only regression check: `3 passed`
- full backend suite:
  - `693 passed, 3 skipped`
- OpenAPI contract suite:
  - `10 passed`
- characterization suite:
  - `7 passed`

## Remaining Deferred Families

See [W2C_PHASE21_DEFERRED_CALLERS.md](C:/final/docs/status/W2C_PHASE21_DEFERRED_CALLERS.md).

## Next Recommendation

Do not jump into high-risk allocator migration yet.

Recommended next step:

- one more review-gated safe pass only if a similarly thin caller family exists

Otherwise:

- stop and perform review before touching registrar, direct SQL, force-majeure, or `OnlineDay` allocators
