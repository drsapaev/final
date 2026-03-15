# Queue Adjacent API Service Cleanup Plan

Scope:
- review detached `backend/app/services/queue_auto_close_api_service.py`
- review detached `backend/app/services/wait_time_analytics_api_service.py`
- prove the mounted queue-adjacent contracts before any deletion
- repair only the narrow live RBAC drift if evidence confirms that the mounted
  owners are calling `require_roles(...)` incorrectly

Evidence:
- the live routes are mounted from
  `backend/app/api/v1/endpoints/queue_auto_close.py` and
  `backend/app/api/v1/endpoints/wait_time_analytics.py`
- `backend/openapi.json` contains the published queue-adjacent routes
- live frontend usage exists for the wait-time analytics surface in
  `frontend/src/components/analytics/WaitTimeAnalytics.jsx`
- no confirmed backend, test, docs, or frontend imports of the detached queue
  duplicate files remain
- diff vs the mounted owners is non-behavioral typing/import drift only
- the mounted endpoint owners currently pass role lists into the SSOT
  `require_roles(...)` dependency instead of positional roles

Why this is safe:
- dedicated endpoint-contract proof lands before deleting the detached files
- the only runtime edit is the narrow SSOT RBAC call-shape fix on the mounted
  owners
- verification includes targeted queue tests, OpenAPI regression, boundary
  checks, and the full backend suite

Out of scope:
- rewriting queue numbering or allocator logic
- changing queue auto-close semantics
- redesigning wait-time analytics calculations
- widening the slice into cashier, EMR, or `/api/v1/2fa/devices*` ownership work
