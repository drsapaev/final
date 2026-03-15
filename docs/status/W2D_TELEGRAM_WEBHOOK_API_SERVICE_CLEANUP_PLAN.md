# Telegram Webhook API Service Cleanup Plan

Scope:
- delete dead router-style duplicate
  `backend/app/services/telegram_webhook_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner
  `telegram_webhook.py`
- `backend/openapi.json` contains the live `/api/v1/telegram/webhook`,
  `/api/v1/telegram/send-message`, and `/api/v1/telegram/bot-info` routes
  served by that owner
- no confirmed backend, test, docs, or frontend import of
  `telegram_webhook_api_service.py` remains
- the service file duplicated mounted router logic instead of acting as a
  consumed service layer

Why this is safe:
- the file was not a mounted owner
- the live Telegram webhook endpoints remain in `telegram_webhook.py`
- removing the duplicate does not change the active Telegram runtime

Out of scope:
- changing Telegram bot behavior
- changing Telegram webhook auth behavior
- removing the mounted `telegram_webhook.py` owner
