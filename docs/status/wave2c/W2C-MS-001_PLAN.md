# W2C-MS-001 Plan

Date: 2026-03-07
Mode: Wave 2C Phase 1
Contract: `.ai-factory/contracts/w2c-ms-001.contract.json`

## Files

- `backend/app/services/queue_status.py`
- `backend/app/repositories/queue_position_api_repository.py`
- `backend/tests/unit/test_queue_status.py`
- `docs/architecture/W2C_STATUS_NORMALIZATION.md`

## Endpoints / Functions

- `QueuePositionApiRepository.list_position_entries`
- central queue status helper functions

## Current Anti-Pattern

Queue read-status subsets are embedded as string literals inside repositories, which
keeps status drift undocumented and makes it easy for read paths to diverge further.

## Target Architecture

- one central queue-status helper for canonical aliases and raw-status groups
- queue-position repository imports its visible-status subset from that helper
- no change to stored status values or public payloads

## Expected Wiring

- `queue_position` read path remains `router -> QueuePositionApiService -> QueuePositionApiRepository`
- repository reads use `queue_status.POSITION_VISIBLE_RAW_STATUSES`

## Risk Level

Low

## Protected Zone Check

No direct protected-zone mutation.
This slice touches queue read behavior only and preserves existing filters.
