# FCM Notifications API Service Cleanup

`backend/app/services/fcm_notifications_api_service.py` was a detached
router-style residue for the mounted FCM endpoint owner.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/fcm_notifications.py` with `prefix="/fcm"`
- `backend/openapi.json` exposes the live `/api/v1/fcm/*` routes owned by the
  mounted endpoint file
- no live source imports of
  `backend/app/services/fcm_notifications_api_service.py` were found in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- `backend/app/services/fcm_notifications_api_service.py` differed from the
  mounted owner only by typing and import drift and no longer owned runtime
  route behavior

Cleanup performed:
- removed `backend/app/services/fcm_notifications_api_service.py`

Effect:
- no mounted runtime route was removed
- live FCM route ownership remains unchanged
- one more dead router-style service residue is gone
