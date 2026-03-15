# Wave 2D OnlineDay Dead Cleanup Status

Date: 2026-03-09
Mode: cleanup-first, safe removal

## Result

`PARTIAL_SUCCESS`

## What was removed

- `backend/app/api/v1/endpoints/online_queue.py`
- `backend/app/api/v1/endpoints/online_queue_legacy.py`

These files were confirmed dead/disabled:

- not mounted
- not imported by live runtime
- not referenced by tests

## What was retained

- `backend/app/crud/queue.py`

## Why it was retained

This file turned out not to be dead for this slice.

Focused verification showed:

- `backend/app/api/v1/endpoints/mobile_api_extended.py` still imports
  `app.crud.queue` as `crud_queue`
- removing the file caused `ImportError` during API bootstrap

So it was restored immediately and excluded from this cleanup slice.

## Validation performed

- bootstrap import check:
  - `python -c "from app.api.v1.api import api_router; ..."`
- `pytest tests/test_openapi_contract.py -q`
- `pytest -q`

## Validation result

- bootstrap import check: passed after restoring `crud/queue.py`
- OpenAPI contract: passed
- full backend suite: passed

## Remaining work for later phases

- support-only OnlineDay mirrors
- live mounted endpoint replacement prep
- separate review/cleanup decision for retained `backend/app/crud/queue.py`

## Cleanup verdict

The dead-cleanup slice succeeded for the two truly dead endpoint modules.

It also found one important blocker:
`backend/app/crud/queue.py` must not be treated as dead without a separate
legacy-runtime review.
