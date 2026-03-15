# Analytics KPI API Service Cleanup Plan

Scope:
- delete dead router-style duplicate
  `backend/app/services/analytics_kpi_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner `analytics_kpi.py`
- `backend/openapi.json` contains the live `/api/v1/analytics/kpi*` routes
- no confirmed backend, test, docs, or frontend import of
  `analytics_kpi_api_service.py` remains
- the service file duplicated mounted router logic instead of acting as a
  consumed service layer

Why this is safe:
- the file was not a mounted owner
- the live analytics KPI endpoints remain in `analytics_kpi.py`
- removing the duplicate does not change the active analytics runtime

Out of scope:
- changing analytics KPI behavior
- changing analytics auth
- removing the mounted `analytics_kpi.py` owner
