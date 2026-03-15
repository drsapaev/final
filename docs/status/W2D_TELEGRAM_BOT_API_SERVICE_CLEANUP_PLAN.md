# Telegram Bot API Service Cleanup Plan

Scope:
- delete dead router-style duplicate
  `backend/app/services/telegram_bot_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner `telegram_bot.py`
- `backend/openapi.json` contains the live `/api/v1/telegram/bot/*` routes
- no confirmed backend, test, docs, or frontend import of
  `telegram_bot_api_service.py` remains
- the service file duplicated mounted router logic instead of acting as a
  consumed service layer

Why this is safe:
- the file was not a mounted owner
- the live Telegram bot endpoints remain in `telegram_bot.py`
- removing the duplicate does not change the active Telegram bot runtime

Out of scope:
- changing Telegram bot behavior
- changing webhook handling behavior
- removing the mounted `telegram_bot.py` owner
