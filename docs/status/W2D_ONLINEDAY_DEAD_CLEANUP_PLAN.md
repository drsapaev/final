# Wave 2D OnlineDay Dead Cleanup Plan

Date: 2026-03-09
Mode: cleanup-first, safe removal

## Target verification

| Target file | Mounted? | Imported by live runtime? | Referenced by tests? | Safe to remove? | Reason considered dead/disabled | Verification method | Proposed cleanup action |
|---|---|---:|---:|---:|---|---|---|
| `backend/app/api/v1/endpoints/online_queue.py` | No | No | No | Yes | Disabled legacy router; `api.py` keeps only a commented-out `include_router(...)` line and does not import the module into live runtime | inspected `backend/app/api/v1/api.py`; repo grep for live imports and test references | Delete file only; no runtime route change expected |
| `backend/app/api/v1/endpoints/online_queue_legacy.py` | No | No | No | Yes | Unmounted QR-compat alias layer with no live router registration | repo grep for imports/references; no mounted include found | Delete file |
| `backend/app/crud/queue.py` | No | Yes | No | No | Initially looked stale, but runtime import verification showed `backend/app/api/v1/endpoints/mobile_api_extended.py` still imports it | repo grep plus bootstrap import failure reproduction, then direct inspection of `mobile_api_extended.py` | Retain file; move it out of this dead-cleanup slice and treat as separate legacy follow-up |

## Notes

- Historical docs and reports still mention these files. That is not a cleanup
  blocker.
- `backend/app/crud/queue.py` is no longer part of the confirmed-dead set for
  this slice.
- Live OnlineDay legacy surfaces remain out of scope:
  - `appointments.open_day()`
  - `appointments.stats()`
  - `appointments.close_day()`
  - `queues.stats()`
  - `queues.next_ticket()`
  - `board.state()`
  - `online_queue.py` service
  - `OnlineDay` model

## Planned validation

- focused import check for `app.api.v1.api`
- `pytest tests/test_openapi_contract.py -q`
- `pytest -q`
