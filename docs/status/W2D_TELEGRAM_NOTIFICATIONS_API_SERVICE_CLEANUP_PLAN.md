# Telegram Notifications API Service Cleanup Plan

Scope:
- delete dead router-style residue
  `backend/app/services/telegram_notifications_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner
  `telegram_notifications.py`
- `backend/openapi.json` contains the live `/api/v1/telegram/*` notification
  routes served by that owner
- no confirmed backend, test, docs, or frontend import of
  `telegram_notifications_api_service.py` remains
- the file was not the mounted owner and represented an older detached router
  implementation for the same Telegram notification surface

Why this is safe:
- the file was not a mounted owner
- the live Telegram notification endpoints remain in
  `telegram_notifications.py`
- removing the residue does not change the active Telegram notification runtime

Out of scope:
- changing Telegram bot behavior
- changing notification delivery behavior
- removing the mounted `telegram_notifications.py` owner
