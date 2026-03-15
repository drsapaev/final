# AI Integration API Service Cleanup Plan

Scope:
- delete dead router-style duplicate
  `backend/app/services/ai_integration_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner `ai_integration.py`
- `backend/openapi.json` contains the live `/api/v1/ai/*` integration routes
  served by that owner
- no confirmed backend, test, docs, or frontend import of
  `ai_integration_api_service.py` remains
- the service file duplicated mounted router logic instead of acting as a
  consumed service layer

Why this is safe:
- the file was not a mounted owner
- the live AI integration endpoints remain in `ai_integration.py`
- removing the duplicate does not change the active AI runtime

Out of scope:
- changing AI integration behavior
- changing AI role gates
- removing the mounted `ai_integration.py` owner
