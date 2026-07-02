# Wave 2C Phase 2.1 Plan

Date: 2026-03-07
Mode: behavior-preserving execution

## Selected Callers

- `backend/app/api/v1/endpoints/online_queue_new.py::join_queue()`
- `backend/app/services/qr_queue_service.py::complete_join_session()`
- `backend/app/services/qr_queue_service.py::complete_join_session_multiple()`

## Files Affected

- `backend/app/api/v1/endpoints/online_queue_new.py`
- `backend/app/services/qr_queue_service.py`
- targeted tests under `backend/tests/unit/`
- targeted integration tests for `/api/v1/online-queue/join`
- queue migration docs and summaries

## Current Path

- selected callers invoke `queue_service.join_queue_with_token(...)` directly

## New Path

- selected callers invoke `QueueDomainService.allocate_ticket(allocation_mode="join_with_token", ...)`
- `QueueDomainService` continues delegating to the existing legacy allocator

## Required Test Coverage

- unit test proving `online_queue_new.join_queue()` uses `QueueDomainService.allocate_ticket()`
- unit tests proving `QRQueueService.complete_join_session*()` use `QueueDomainService.allocate_ticket()`
- integration tests for `/api/v1/online-queue/join` success and duplicate reuse
- existing QR join characterization/integration tests remain green
- full backend suite, OpenAPI contract suite, and characterization suite

## Rollback Notes

- revert caller swap if any of these change:
  - queue number assignment
  - duplicate detection outcome
  - response payload shape
  - `queue_time` behavior
  - QR join success/duplicate scenarios
- do not extend the migration to registrar, force-majeure, or legacy allocators inside this pass
