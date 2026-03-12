# Analytics Simple Endpoint Cleanup Plan

Scope:
- delete dead duplicate endpoint artifact
  `backend/app/api/v1/endpoints/analytics_simple.py`

Evidence:
- `backend/app/api/v1/api.py` does not mount `analytics_simple.router`
- `backend/openapi.json` already includes the analytics routes under the mounted
  `analytics.py` owner
- no confirmed frontend or backend runtime import of the dead endpoint module
  remains

Why this is safe:
- the endpoint was not mounted, so deleting it cannot change runtime routing
- the same route shapes already belong to the mounted analytics owner

Out of scope:
- cleanup of `analytics_simple_api_service.py`
- analytics behavior changes
- redesign of mounted analytics routes
