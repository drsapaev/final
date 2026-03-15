# Telegram Bot API Service Cleanup

`backend/app/services/telegram_bot_api_service.py` was a detached
router-style duplicate of the mounted Telegram bot endpoint owner.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/telegram_bot.py`
- `backend/openapi.json` exposes the live `/api/v1/telegram/bot/*` surface
  from the mounted endpoint owner
- no live source imports of
  `backend/app/services/telegram_bot_api_service.py` were found in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- `backend/app/services/telegram_bot_api_service.py` duplicated the router
  logic already owned by
  `backend/app/api/v1/endpoints/telegram_bot.py`

Cleanup performed:
- removed `backend/app/services/telegram_bot_api_service.py`

Effect:
- no mounted runtime route was removed
- live Telegram bot route ownership remains unchanged
- one more dead router-style service duplicate is gone
