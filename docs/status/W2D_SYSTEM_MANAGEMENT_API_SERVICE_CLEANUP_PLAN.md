# System Management API Service Cleanup Plan

Scope:
- delete dead router-style duplicate
  `backend/app/services/system_management_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner
  `system_management.py`
- `backend/openapi.json` contains the live `/api/v1/system/*` routes
- no confirmed backend, test, docs, or frontend import of
  `system_management_api_service.py` remains
- the service file duplicated mounted router logic instead of acting as a
  consumed service layer

Why this is safe:
- the file was not a mounted owner
- the live system endpoints remain in `system_management.py`
- removing the duplicate does not change the active backup or monitoring
  runtime

Out of scope:
- changing backup or monitoring behavior
- changing system endpoint auth rules
- removing the mounted `system_management.py` owner
