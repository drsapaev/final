# AI Gateway API Service Cleanup Plan

Scope:
- delete dead router-style residue
  `backend/app/services/ai_gateway_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner `ai_gateway.py`
- `backend/openapi.json` contains the live `/api/v1/ai/v2/*` routes served by
  that owner
- no confirmed backend, test, docs, or frontend import of
  `ai_gateway_api_service.py` remains
- the file was not the mounted owner and represented an older detached router
  implementation for the same AI gateway surface

Why this is safe:
- the file was not a mounted owner
- the live AI gateway endpoints remain in `ai_gateway.py`
- removing the residue does not change the active AI gateway runtime

Out of scope:
- changing AI gateway behavior
- changing AI RBAC behavior
- removing the mounted `ai_gateway.py` owner
