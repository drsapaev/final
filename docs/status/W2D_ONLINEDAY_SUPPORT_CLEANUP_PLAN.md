# Wave 2D OnlineDay Support Cleanup Plan

Date: 2026-03-09
Mode: cleanup-first, safe removal

## Target verification

| Target file | Mounted? | Imported by live runtime? | Imported only as mirror/wrapper? | Safe to remove? | Reason considered support-only | Verification method | Proposed cleanup action |
|---|---:|---:|---:|---:|---|---|---|
| `backend/app/services/online_queue_api_service.py` | No | No | Yes | Yes | Duplicate wrapper surface for the already-removed disabled `online_queue` endpoint family | inspected file content; repo grep found no live imports or tests | Delete file |
| `backend/app/services/appointments_api_service.py` | No | No | Yes | No | Duplicate appointments/legacy queue wrapper module; not the mounted `appointments.py` runtime owner, but still enforced by architecture boundary tests as a service artifact | inspected file content; repo grep for `AppointmentsApiService`; full backend suite failure showed `tests/unit/test_service_repository_boundary.py` reads the file by path | Retain file for now; move follow-up to later replacement/deprecation phase |
| `backend/app/services/board_api_service.py` | No | No | Yes | Yes | Duplicate board wrapper over `load_stats()`, not the mounted `board.py` runtime owner | inspected file content; repo grep found no imports or tests | Delete file |
| `backend/app/services/queues_api_service.py` | No | No | Yes | Yes | Duplicate queues wrapper over legacy `load_stats()` / `issue_next_ticket()`, not the mounted `queues.py` runtime owner | inspected file content; repo grep found no imports or tests | Delete file |

## Notes

- This slice intentionally excludes live OnlineDay runtime owners:
  - `backend/app/api/v1/endpoints/appointments.py`
  - `backend/app/api/v1/endpoints/queues.py`
  - `backend/app/api/v1/endpoints/board.py`
  - `backend/app/services/online_queue.py`
  - `backend/app/models/online.py`
- `backend/app/crud/queue.py` also remains out of scope because it was already
  proven live through `mobile_api_extended.py`.

## Planned validation

- bootstrap import check for `app.api.v1.api`
- `pytest tests/test_openapi_contract.py -q`
- `pytest -q`

## Outcome update

- Removed as planned:
  - `backend/app/services/online_queue_api_service.py`
  - `backend/app/services/board_api_service.py`
  - `backend/app/services/queues_api_service.py`
- Retained:
  - `backend/app/services/appointments_api_service.py`

`appointments_api_service.py` turned out to be support-only for runtime, but not
yet removable for the repository as a whole because the service-boundary suite
still treats it as a required artifact.
