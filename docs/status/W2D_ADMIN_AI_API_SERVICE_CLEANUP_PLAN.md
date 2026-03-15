# Admin AI API Service Cleanup Plan

Scope:
- delete dead router-style residue
  `backend/app/services/admin_ai_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner `admin_ai.py`
- `backend/openapi.json` contains the live `/api/v1/admin/ai/*` routes served
  by that owner
- no confirmed backend, test, docs, or frontend import of
  `admin_ai_api_service.py` remains
- the file was not the mounted owner and represented an older detached router
  implementation for the same admin AI surface

Why this is safe:
- the file was not a mounted owner
- the live admin AI endpoints remain in `admin_ai.py`
- removing the residue does not change the active admin AI runtime

Out of scope:
- changing AI provider behavior
- changing admin AI authorization behavior
- removing the mounted `admin_ai.py` owner
