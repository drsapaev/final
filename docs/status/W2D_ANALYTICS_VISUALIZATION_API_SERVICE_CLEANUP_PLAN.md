# Analytics Visualization API Service Cleanup Plan

Scope:
- delete dead router-style duplicate
  `backend/app/services/analytics_visualization_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner
  `analytics_visualization.py`
- `backend/openapi.json` contains the live
  `/api/v1/analytics/visualization/*` routes served by that owner
- no confirmed backend, test, docs, or frontend import of
  `analytics_visualization_api_service.py` remains
- the service file duplicated mounted router logic instead of acting as a
  consumed service layer

Why this is safe:
- the file was not a mounted owner
- the live analytics visualization endpoints remain in
  `analytics_visualization.py`
- removing the duplicate does not change the active analytics visualization
  runtime

Out of scope:
- changing analytics visualization behavior
- changing analytics visualization auth gates
- removing the mounted `analytics_visualization.py` owner
