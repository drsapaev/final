# Print API Service Cleanup Plan

Scope:
- delete dead router-style duplicate
  `backend/app/services/print_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner `print.py`
- `backend/openapi.json` contains the live `/api/v1/print/*` routes
- no confirmed backend, test, docs, or frontend import of
  `print_api_service.py` remains
- the service file duplicated mounted router logic instead of acting as a
  consumed service layer

Why this is safe:
- the file was not a mounted owner
- the live print endpoints remain in `print.py`
- removing the duplicate does not change the active print runtime

Out of scope:
- changing print endpoint behavior
- changing print auth or output shape
- removing the mounted `print.py` owner
