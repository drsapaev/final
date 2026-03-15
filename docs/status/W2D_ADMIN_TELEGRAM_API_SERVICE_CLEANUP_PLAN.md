# Admin Telegram API Service Cleanup Plan

Scope:
- delete dead router-style duplicate
  `backend/app/services/admin_telegram_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner
  `admin_telegram.py`
- `backend/openapi.json` contains the live `/api/v1/admin/telegram/*` routes
- no confirmed backend, test, docs, or frontend import of
  `admin_telegram_api_service.py` remains
- the service file duplicated mounted router logic instead of acting as a
  consumed service layer

Why this is safe:
- the file was not a mounted owner
- the live admin Telegram endpoints remain in `admin_telegram.py`
- removing the duplicate does not change the active admin Telegram runtime

Out of scope:
- changing admin Telegram behavior
- changing Telegram provider behavior
- removing the mounted `admin_telegram.py` owner
