# AI Analytics API Service Cleanup

`backend/app/services/ai_analytics_api_service.py` was a detached
router-style duplicate of the mounted AI analytics endpoint owner.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/ai_analytics.py`
- `backend/openapi.json` exposes the live `/api/v1/analytics/ai/*` surface
  from the mounted endpoint owner
- no live source imports of
  `backend/app/services/ai_analytics_api_service.py` were found in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- `backend/app/services/ai_analytics_api_service.py` duplicated the router
  logic already owned by
  `backend/app/api/v1/endpoints/ai_analytics.py`

Cleanup performed:
- removed `backend/app/services/ai_analytics_api_service.py`

Effect:
- no mounted runtime route was removed
- live AI analytics route ownership remains unchanged
- one more dead router-style service duplicate is gone
