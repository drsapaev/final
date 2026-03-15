# Mobile API Extended API Service Cleanup Plan

Scope:
- delete dead router-style residue
  `backend/app/services/mobile_api_extended_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner
  `mobile_api_extended.py`
- `backend/openapi.json` contains the live `/api/v1/mobile/*` routes served by
  that owner
- no confirmed backend, test, docs, or frontend import of
  `mobile_api_extended_api_service.py` remains
- the file was not the mounted owner and represented an older detached router
  implementation for the same extended mobile surface

Why this is safe:
- the file was not a mounted owner
- the live extended mobile endpoints remain in `mobile_api_extended.py`
- removing the residue does not change the active extended mobile runtime

Out of scope:
- changing mobile auth behavior
- changing appointment, queue, or notification logic
- removing the mounted `mobile_api_extended.py` owner
