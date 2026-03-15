# Analytics API Service Cleanup Plan

Scope:
- delete dead router-style residue
  `backend/app/services/analytics_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner `analytics.py`
- `backend/openapi.json` contains the live `/api/v1/analytics/*` routes served
  by that owner
- no confirmed backend, test, docs, or frontend import of
  `analytics_api_service.py` remains
- the file was not the mounted owner and represented an older detached router
  implementation for the same analytics surface

Why this is safe:
- the file was not a mounted owner
- the live analytics endpoints remain in `analytics.py`
- removing the residue does not change the active analytics runtime

Out of scope:
- changing analytics behavior
- changing analytics auth gates
- removing the mounted `analytics.py` owner
