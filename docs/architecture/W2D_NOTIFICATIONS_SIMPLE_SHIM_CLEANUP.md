# Notifications Simple Shim Cleanup

`backend/app/api/v1/endpoints/notifications_simple.py` and
`backend/app/services/notifications_simple_api_service.py` formed a detached
legacy shim pair.

Verified facts:
- `backend/app/api/v1/api.py` mounts `notifications.router`,
  `notification_websocket.router`, `registrar_notifications.router`,
  `telegram_notifications.router`, and `fcm_notifications.router`, but does not
  mount `notifications_simple.router`
- no live source imports of `notifications_simple.py` or
  `notifications_simple_api_service.py` were found in `backend/app`,
  `backend/tests`, `docs`, or `frontend`
- the endpoint and service files were byte-identical stub implementations

Cleanup performed:
- removed `backend/app/api/v1/endpoints/notifications_simple.py`
- removed `backend/app/services/notifications_simple_api_service.py`

Effect:
- no runtime route was removed, because the shim endpoint was never mounted
- no live service owner changed, because the service shim had no runtime
  imports
- the mounted notifications surface remains owned by the existing non-simple
  routers already registered in `backend/app/api/v1/api.py`
