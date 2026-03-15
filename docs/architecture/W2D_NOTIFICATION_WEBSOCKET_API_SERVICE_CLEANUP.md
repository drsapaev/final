# Notification Websocket API Service Cleanup

`backend/app/services/notification_websocket_api_service.py` was a detached
router-style residue for the mounted notification websocket endpoint owner.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/notification_websocket.py`
- the mounted endpoint owner defines only
  `@router.websocket("/ws/notifications/connect")`
- websocket routes are not represented in `backend/openapi.json`, so the
  absence of this path from the OpenAPI contract is expected
- no live source imports of
  `backend/app/services/notification_websocket_api_service.py` were found in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- `backend/app/services/notification_websocket_api_service.py` differed from
  the mounted owner only by import and whitespace drift plus one unused local
  receive binding difference, without changing runtime behavior

Cleanup performed:
- removed `backend/app/services/notification_websocket_api_service.py`

Effect:
- no mounted runtime route was removed
- live notification websocket ownership remains unchanged
- one more dead router-style service residue is gone
