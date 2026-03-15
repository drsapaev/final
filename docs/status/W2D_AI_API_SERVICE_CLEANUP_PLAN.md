# AI API Service Cleanup Plan

Scope:
- delete dead router-style residue `backend/app/services/ai_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner `ai.py`
- `backend/openapi.json` contains the live `/api/v1/ai/*` routes served by
  that owner
- no confirmed backend, test, docs, or frontend import of `ai_api_service.py`
  remains
- the file was not the mounted owner and represented an older detached router
  implementation for the same AI surface

Why this is safe:
- the file was not a mounted owner
- the live AI endpoints remain in `ai.py`
- removing the residue does not change the active AI runtime

Out of scope:
- changing AI behavior
- changing AI authorization behavior
- removing the mounted `ai.py` owner
