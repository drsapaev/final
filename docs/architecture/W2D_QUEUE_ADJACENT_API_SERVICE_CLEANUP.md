# Queue Adjacent API Service Cleanup

`backend/app/services/queue_auto_close_api_service.py` and
`backend/app/services/wait_time_analytics_api_service.py` were handled as a
protected queue-adjacent duplicate cluster, not as blind-delete candidates.

Verified facts:
- `backend/app/api/v1/api.py` mounts the live owners:
  - `backend/app/api/v1/endpoints/queue_auto_close.py` under
    `/api/v1/admin/queue-auto-close`
  - `backend/app/api/v1/endpoints/wait_time_analytics.py` under
    `/api/v1/analytics/wait-time`
- `backend/openapi.json` publishes both live surfaces, including:
  - `/api/v1/admin/queue-auto-close/check-and-close`
  - `/api/v1/admin/queue-auto-close/pending-close`
  - `/api/v1/admin/queue-auto-close/force-close/{queue_id}`
  - `/api/v1/admin/queue-auto-close/auto-close-status`
  - `/api/v1/analytics/wait-time/wait-time-analytics`
  - `/api/v1/analytics/wait-time/real-time-wait-estimates`
  - `/api/v1/analytics/wait-time/service-wait-analytics`
  - `/api/v1/analytics/wait-time/wait-time-summary`
  - `/api/v1/analytics/wait-time/wait-time-comparison`
  - `/api/v1/analytics/wait-time/wait-time-heatmap`
- live frontend usage remains on the mounted wait-time surface in
  `frontend/src/components/analytics/WaitTimeAnalytics.jsx`
- no live imports of either detached service remained in `backend/app`,
  `backend/tests`, `docs`, or `frontend`
- diff vs the mounted owners was only typing/import drift
- queue audit exposed one narrow mounted-owner runtime bug shared by both live
  endpoint modules: `require_roles(...)` was called with a list instead of
  positional roles, which breaks the SSOT security dependency

Cleanup performed:
- added `backend/tests/integration/test_queue_protected_endpoint_contract.py`
  to protect both mounted queue-adjacent contracts
- repaired the mounted owners in:
  - `backend/app/api/v1/endpoints/queue_auto_close.py`
  - `backend/app/api/v1/endpoints/wait_time_analytics.py`
  by switching `require_roles([...])` to positional `require_roles(...)`
- deleted detached `backend/app/services/queue_auto_close_api_service.py`
- deleted detached `backend/app/services/wait_time_analytics_api_service.py`

Effect:
- no mounted queue-adjacent route was removed
- the detached duplicate pair is gone
- the live queue-adjacent endpoints now follow the actual SSOT RBAC contract
- protected queue cleanup moved forward without rewriting queue allocation,
  numbering, or timing algorithms
