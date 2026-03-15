# Telegram Integration API Service Cleanup Plan

Scope:
- delete dead router-style residue
  `backend/app/services/telegram_integration_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner
  `telegram_integration.py`
- `backend/openapi.json` contains the live `/api/v1/telegram/*` integration
  routes served by that owner
- no confirmed backend, test, docs, or frontend import of
  `telegram_integration_api_service.py` remains
- the file was not the mounted owner and represented an older detached router
  implementation for the same Telegram integration surface

Why this is safe:
- the file was not a mounted owner
- the live Telegram integration endpoints remain in `telegram_integration.py`
- removing the residue does not change the active Telegram integration runtime

Out of scope:
- changing Telegram delivery behavior
- changing Telegram webhook behavior
- removing the mounted `telegram_integration.py` owner
