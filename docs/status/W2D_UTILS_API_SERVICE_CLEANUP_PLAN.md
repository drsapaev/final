# Utils API Service Cleanup Plan

Scope:
- delete dead router-style residue `backend/app/services/utils_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner `utils.py`
- `backend/openapi.json` contains the live `/api/v1/utils/link-preview` route
  served by that owner
- no confirmed backend, test, docs, or frontend import of `utils_api_service.py`
  remains
- the file was not the mounted owner and represented an older detached router
  implementation for the same utils surface

Why this is safe:
- the file was not a mounted owner
- the live utils endpoint remains in `utils.py`
- removing the residue does not change the active utils runtime

Out of scope:
- changing link preview behavior
- changing utils route authorization behavior
- removing the mounted `utils.py` owner
