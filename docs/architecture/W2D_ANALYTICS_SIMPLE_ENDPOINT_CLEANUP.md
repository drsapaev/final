# Analytics Simple Endpoint Cleanup

`backend/app/api/v1/endpoints/analytics_simple.py` was a dead duplicate
endpoint artifact.

Verified facts:
- `backend/app/api/v1/api.py` did not include `analytics_simple.router`
- `backend/openapi.json` already exposed `/api/v1/analytics/quick-stats`,
  `/api/v1/analytics/dashboard`, and `/api/v1/analytics/trends` from the
  mounted `analytics.py` router
- no live source imports of `backend/app/api/v1/endpoints/analytics_simple.py`
  were found in `backend/app` or `backend/tests`
- the file duplicated the quick-stats and dashboard routes already owned by
  `analytics.py`

Cleanup performed:
- removed `backend/app/api/v1/endpoints/analytics_simple.py`

Effect:
- no runtime route was removed, because the endpoint was never mounted
- the live analytics routes remain owned by `backend/app/api/v1/endpoints/analytics.py`
- one more dead duplicate endpoint artifact is gone
