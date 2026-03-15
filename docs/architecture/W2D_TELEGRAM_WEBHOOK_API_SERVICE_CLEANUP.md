# Telegram Webhook API Service Cleanup

`backend/app/services/telegram_webhook_api_service.py` was a detached
router-style duplicate of the mounted Telegram webhook endpoint owner.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/telegram_webhook.py` with `prefix="/telegram"`
- `backend/openapi.json` exposes the live `/api/v1/telegram/webhook`,
  `/api/v1/telegram/send-message`, and `/api/v1/telegram/bot-info` routes
  owned by the mounted endpoint file
- no live source imports of
  `backend/app/services/telegram_webhook_api_service.py` were found in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- `backend/app/services/telegram_webhook_api_service.py` duplicated the router
  logic already owned by `backend/app/api/v1/endpoints/telegram_webhook.py`,
  with only minor typing and `operation_id` drift

Cleanup performed:
- removed `backend/app/services/telegram_webhook_api_service.py`

Effect:
- no mounted runtime route was removed
- live Telegram webhook route ownership remains unchanged
- one more dead router-style service duplicate is gone
