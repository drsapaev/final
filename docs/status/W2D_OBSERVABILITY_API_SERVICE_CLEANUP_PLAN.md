# Observability API Service Cleanup Plan

Scope:
- delete dead router-style duplicate
  `backend/app/services/observability_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner
  `observability.py`
- `backend/openapi.json` contains the live `/api/v1/observability/*` routes
- no confirmed backend, test, docs, or frontend import of
  `observability_api_service.py` remains
- the service file was a byte-identical duplicate of the mounted endpoint
  owner

Why this is safe:
- the file was not a mounted owner
- the live observability endpoints remain in `observability.py`
- removing the duplicate does not change the active metrics or alert runtime

Out of scope:
- changing observability endpoint behavior
- changing observability auth or scrape exposure
- removing the mounted `observability.py` owner
