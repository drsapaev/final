# AI Tracking Endpoint Cleanup Plan

Scope:
- delete dead endpoint artifact `backend/app/api/v1/endpoints/ai_tracking.py`

Evidence:
- `backend/app/api/v1/api.py` does not mount `ai_tracking.router`
- `backend/openapi.json` does not contain the endpoint file's expected
  `/api/v1/ai/models/*`, `/api/v1/ai/providers/stats`, or
  `/api/v1/ai/requests/recent` paths
- no confirmed backend or test import of the endpoint module remains
- the supporting service and repository layers are independently present and
  tested

Why this is safe:
- the endpoint was not mounted, so deleting it cannot change runtime routing
- the AI tracking service layer remains intact for any future mounted owner

Out of scope:
- removing `ai_tracking_api_service.py`
- removing `ai_tracking_api_repository.py`
- redesign of mounted AI routes
