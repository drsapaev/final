# Monitoring Endpoint Cleanup Plan

Scope:
- delete dead endpoint artifact `backend/app/api/v1/endpoints/monitoring.py`
- correct stale API reference that still advertised `/admin/monitoring`

Evidence:
- `backend/app/api/v1/api.py` does not mount `monitoring.router`
- live admin monitoring surface already exists under `system_management.router`
- no confirmed frontend or backend runtime consumer of `/admin/monitoring/*` remains

Why this is safe:
- the endpoint was not mounted, so deleting it cannot change runtime routing
- API docs are corrected toward the already-mounted `/system/monitoring/*` surface

Out of scope:
- broader observability redesign
- cleanup of `system_management` monitoring endpoints
- metrics/alerts behavior changes
