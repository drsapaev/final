# Admin Display API Service Cleanup Plan

Scope:
- delete dead router-style duplicate
  `backend/app/services/admin_display_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner
  `admin_display.py`
- `backend/openapi.json` contains the live `/api/v1/admin/display/*` routes
- no confirmed backend, test, docs, or frontend import of
  `admin_display_api_service.py` remains
- the service file duplicated mounted router logic instead of acting as a
  consumed service layer

Why this is safe:
- the file was not a mounted owner
- the live admin display endpoints remain in `admin_display.py`
- removing the duplicate does not change the active admin display runtime

Out of scope:
- changing admin display behavior
- changing admin display auth
- removing the mounted `admin_display.py` owner
