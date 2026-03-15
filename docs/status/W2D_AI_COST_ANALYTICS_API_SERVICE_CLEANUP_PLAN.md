# AI Cost Analytics API Service Cleanup Plan

Scope:
- delete dead router-style duplicate
  `backend/app/services/ai_cost_analytics_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner
  `ai_cost_analytics.py`
- `backend/openapi.json` contains the live `/api/v1/ai/analytics/*` routes
  served by that owner
- no confirmed backend, test, docs, or frontend import of
  `ai_cost_analytics_api_service.py` remains
- the service file duplicated mounted router logic instead of acting as a
  consumed service layer

Why this is safe:
- the file was not a mounted owner
- the live AI cost analytics endpoints remain in `ai_cost_analytics.py`
- removing the duplicate does not change the active AI cost analytics runtime

Out of scope:
- changing AI permission behavior
- changing AI cost tracking behavior
- removing the mounted `ai_cost_analytics.py` owner
