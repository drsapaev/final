# FCM Notifications API Service Cleanup Plan

Scope:
- delete dead router-style residue
  `backend/app/services/fcm_notifications_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner
  `fcm_notifications.py`
- `backend/openapi.json` contains the live `/api/v1/fcm/*` routes served by
  that owner
- no confirmed backend, test, docs, or frontend import of
  `fcm_notifications_api_service.py` remains
- the file was not the mounted owner and represented an older detached router
  implementation for the same FCM surface

Why this is safe:
- the file was not a mounted owner
- the live FCM endpoints remain in `fcm_notifications.py`
- removing the residue does not change the active FCM runtime

Out of scope:
- changing FCM behavior
- changing push notification delivery logic
- removing the mounted `fcm_notifications.py` owner
