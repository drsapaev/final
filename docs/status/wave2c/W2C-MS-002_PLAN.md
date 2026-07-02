# W2C-MS-002 Plan

Date: 2026-03-07
Mode: Wave 2C Phase 1 continuation
Contract: `.ai-factory/contracts/w2c-ms-002.contract.json`

## Files

- `backend/app/api/v1/endpoints/queue_limits.py`
- `backend/app/repositories/queue_read_repository.py`
- `backend/app/services/queue_domain_service.py`
- `backend/tests/architecture/test_w2c_queue_boundaries.py`
- `backend/tests/unit/test_queue_domain_service.py`

## Handlers

- `GET /queue-status`

## Current DB Access Pattern

The queue-limits read model lives in `QueueLimitsApiService`, which uses
`QueueLimitsRepository` to iterate active doctors, find the queue for a day, and count
entries. The current runtime lookup uses `doctor.user_id` when querying
`DailyQueue.specialist_id`.

## Target Wiring

`router -> QueueDomainService -> QueueReadRepository`

Not included in this slice:

- `GET /queue-limits`
- `PUT /queue-limits`
- `PUT /doctor-queue-limit`
- `POST /reset-queue-limits`

## Risk Analysis

Low to medium.

Main risk is not queue mutation; it is accidental cleanup of existing runtime drift.
This slice must preserve current lookup behavior exactly, including the `doctor.user_id`
based queue lookup.

## Runtime Invariants That Must Not Change

- current `doctor.user_id` based queue lookup in limits read path
- response schema of `GET /queue-status`
- queue entry counting behavior
- queue opened/online available flags
- numbering, duplicate, fairness, visit lifecycle, and QR rules
