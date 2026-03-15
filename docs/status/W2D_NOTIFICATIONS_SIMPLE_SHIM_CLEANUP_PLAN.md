# Notifications Simple Shim Cleanup Plan

Scope:
- delete dead endpoint artifact `backend/app/api/v1/endpoints/notifications_simple.py`
- delete duplicate dead mirror `backend/app/services/notifications_simple_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` does not mount `notifications_simple.router`
- mounted notifications behavior already belongs to `notifications`,
  `notification_websocket`, `registrar_notifications`, `telegram_notifications`,
  and `fcm_notifications`
- no confirmed frontend, backend runtime, test, or docs imports of the shim
  pair remain
- the endpoint and service files are byte-identical stub implementations

Why this is safe:
- the endpoint was not mounted, so deleting it cannot change runtime routing
- the service file had no live imports, so deleting it cannot change mounted
  runtime behavior

Out of scope:
- redesign of the mounted notifications APIs
- cleanup of live notifications endpoints
- notification delivery behavior changes
