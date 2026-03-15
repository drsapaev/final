# Notification Websocket API Service Cleanup Plan

Scope:
- delete dead router-style residue
  `backend/app/services/notification_websocket_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner
  `notification_websocket.py`
- the mounted owner exposes only a websocket route, so it is expected not to
  appear in `backend/openapi.json`
- no confirmed backend, test, docs, or frontend import of
  `notification_websocket_api_service.py` remains
- the file was not the mounted owner and represented an older detached router
  implementation for the same websocket surface

Why this is safe:
- the file was not a mounted owner
- the live notification websocket endpoint remains in
  `notification_websocket.py`
- removing the residue does not change the active websocket runtime

Out of scope:
- changing websocket authentication behavior
- changing notification delivery behavior
- removing the mounted `notification_websocket.py` owner
