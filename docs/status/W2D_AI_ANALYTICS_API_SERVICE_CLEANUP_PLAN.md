# AI Analytics API Service Cleanup Plan

Scope:
- delete dead router-style duplicate
  `backend/app/services/ai_analytics_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner `ai_analytics.py`
- `backend/openapi.json` contains the live `/api/v1/analytics/ai/*` routes
- no confirmed backend, test, docs, or frontend import of
  `ai_analytics_api_service.py` remains
- the service file duplicated mounted router logic instead of acting as a
  consumed service layer

Why this is safe:
- the file was not a mounted owner
- the live AI analytics endpoints remain in `ai_analytics.py`
- removing the duplicate does not change the active AI analytics runtime

Out of scope:
- changing AI analytics behavior
- changing analytics auth
- removing the mounted `ai_analytics.py` owner
