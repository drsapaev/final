# Analytics Predictive API Service Cleanup

`backend/app/services/analytics_predictive_api_service.py` was a detached
router-style duplicate of the mounted analytics predictive endpoint owner.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/analytics_predictive.py`
- `backend/openapi.json` exposes the live `/api/v1/analytics/predictive*`
  surface from the mounted endpoint owner
- no live source imports of
  `backend/app/services/analytics_predictive_api_service.py` were found in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- `backend/app/services/analytics_predictive_api_service.py` duplicated the
  router logic already owned by
  `backend/app/api/v1/endpoints/analytics_predictive.py`

Cleanup performed:
- removed `backend/app/services/analytics_predictive_api_service.py`

Effect:
- no mounted runtime route was removed
- live analytics predictive route ownership remains unchanged
- one more dead router-style service duplicate is gone
