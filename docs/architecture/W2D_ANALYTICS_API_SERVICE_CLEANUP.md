# Analytics API Service Cleanup

`backend/app/services/analytics_api_service.py` was a detached router-style
residue for the mounted analytics endpoint owner.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/analytics.py` with `prefix="/analytics"`
- `backend/openapi.json` exposes the live `/api/v1/analytics/quick-stats`,
  `/api/v1/analytics/dashboard`, and `/api/v1/analytics/trends` routes owned
  by the mounted endpoint file
- no live source imports of `backend/app/services/analytics_api_service.py`
  were found in `backend/app`, `backend/tests`, `docs`, or `frontend`
- `backend/app/services/analytics_api_service.py` still contained an older
  router-style implementation for the same analytics surface, while the mounted
  owner now delegates quick stats and dashboard reads through
  `AnalyticsSimpleApiService`

Cleanup performed:
- removed `backend/app/services/analytics_api_service.py`

Effect:
- no mounted runtime route was removed
- live analytics route ownership remains unchanged
- one more dead router-style service residue is gone
