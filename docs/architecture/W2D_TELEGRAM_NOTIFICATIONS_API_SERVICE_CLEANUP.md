# Telegram Notifications API Service Cleanup

`backend/app/services/telegram_notifications_api_service.py` was a detached
router-style residue for the mounted Telegram notifications endpoint owner.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/telegram_notifications.py` with
  `prefix="/telegram"`
- `backend/openapi.json` exposes the live `/api/v1/telegram/*` notification
  routes owned by the mounted endpoint file, including
  `send-appointment-reminder`, `send-lab-results`,
  `send-payment-confirmation`, and `broadcast-message`
- no live source imports of
  `backend/app/services/telegram_notifications_api_service.py` were found in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- `backend/app/services/telegram_notifications_api_service.py` differed from
  the mounted owner only by stale imports and typing drift and no longer owned
  runtime route behavior

Cleanup performed:
- removed `backend/app/services/telegram_notifications_api_service.py`

Effect:
- no mounted runtime route was removed
- live Telegram notification route ownership remains unchanged
- one more dead router-style service residue is gone
