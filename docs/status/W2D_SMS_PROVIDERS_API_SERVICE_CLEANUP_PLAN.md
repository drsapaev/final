# SMS Providers API Service Cleanup Plan

Scope:
- delete dead router-style residue
  `backend/app/services/sms_providers_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner `sms_providers.py`
- `backend/openapi.json` contains the live `/api/v1/sms/*` routes served by
  that owner
- no confirmed backend, test, docs, or frontend import of
  `sms_providers_api_service.py` remains
- the file was not the mounted owner and represented an older detached router
  implementation for the same SMS provider surface

Why this is safe:
- the file was not a mounted owner
- the live SMS provider endpoints remain in `sms_providers.py`
- removing the residue does not change the active SMS provider runtime

Out of scope:
- changing SMS provider integrations
- changing SMS delivery behavior
- removing the mounted `sms_providers.py` owner
