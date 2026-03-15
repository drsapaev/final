# Analytics Export API Service Cleanup Plan

Scope:
- delete dead router-style duplicate
  `backend/app/services/analytics_export_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner
  `analytics_export.py`
- `backend/openapi.json` contains the live `/api/v1/analytics/export/*`
  routes served by that owner
- no confirmed backend, test, docs, or frontend import of
  `analytics_export_api_service.py` remains
- the service file duplicated mounted router logic instead of acting as a
  consumed service layer

Why this is safe:
- the file was not a mounted owner
- the live analytics export endpoints remain in `analytics_export.py`
- removing the duplicate does not change the active analytics export runtime

Out of scope:
- changing analytics export behavior
- changing analytics export auth gates
- removing the mounted `analytics_export.py` owner
