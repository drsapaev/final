# Queue Adjacent API Service Cleanup Status

Status: completed

What changed:
- added dedicated queue-adjacent endpoint contract tests
- repaired the mounted `queue_auto_close.py` and `wait_time_analytics.py`
  owners to call `require_roles(...)` with positional roles
- deleted `backend/app/services/queue_auto_close_api_service.py`
- deleted `backend/app/services/wait_time_analytics_api_service.py`

Validation:
- targeted queue/OpenAPI/boundary verification passes
- full backend suite passes

Result:
- the queue-adjacent duplicate bucket is no longer active
- mounted `/api/v1/admin/queue-auto-close/*` and
  `/api/v1/analytics/wait-time/*` behavior stays intact
- the next honest protected follow-up shifts to EMR/clinical plan-gated audit
