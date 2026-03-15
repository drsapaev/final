# Cloud Printing API Service Cleanup Plan

Scope:
- delete dead router-style duplicate
  `backend/app/services/cloud_printing_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner
  `cloud_printing.py`
- `backend/openapi.json` contains the live `/api/v1/cloud-printing/*` routes
- no confirmed backend, test, docs, or frontend import of
  `cloud_printing_api_service.py` remains
- the service file duplicated mounted router logic instead of acting as a
  consumed service layer

Why this is safe:
- the file was not a mounted owner
- the live cloud printing endpoints remain in `cloud_printing.py`
- removing the duplicate does not change the active cloud-printing runtime

Out of scope:
- changing cloud printing behavior
- changing printer provider behavior
- removing the mounted `cloud_printing.py` owner
