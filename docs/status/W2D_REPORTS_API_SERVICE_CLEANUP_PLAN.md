# Reports API Service Cleanup Plan

Scope:
- delete dead router-style residue
  `backend/app/services/reports_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner `reports.py`
- `backend/openapi.json` contains the live `/api/v1/reports/*` routes served
  by that owner
- no confirmed backend, test, docs, or frontend import of
  `reports_api_service.py` remains
- the file was not the mounted owner and represented an older detached router
  implementation for the same reports surface

Why this is safe:
- the file was not a mounted owner
- the live reports endpoints remain in `reports.py`
- removing the residue does not change the active reports runtime

Out of scope:
- changing reporting behavior
- changing report generation or cleanup behavior
- removing the mounted `reports.py` owner
