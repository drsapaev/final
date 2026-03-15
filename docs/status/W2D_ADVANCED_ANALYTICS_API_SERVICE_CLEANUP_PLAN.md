# Advanced Analytics API Service Cleanup Plan

Scope:
- delete dead router-style duplicate
  `backend/app/services/advanced_analytics_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner
  `advanced_analytics.py`
- `backend/openapi.json` contains the live `/api/v1/analytics/advanced/*`
  routes
- no confirmed backend, test, docs, or frontend import of
  `advanced_analytics_api_service.py` remains
- the service file duplicated mounted router logic instead of acting as a
  consumed service layer

Why this is safe:
- the file was not a mounted owner
- the live advanced analytics endpoints remain in `advanced_analytics.py`
- removing the duplicate does not change the active analytics runtime

Out of scope:
- changing advanced analytics behavior
- changing analytics auth
- removing the mounted `advanced_analytics.py` owner
