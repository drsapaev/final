# SMS Providers API Service Cleanup

`backend/app/services/sms_providers_api_service.py` was a detached router-style
residue for the mounted SMS providers endpoint owner.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/sms_providers.py` with `prefix="/sms"`
- `backend/openapi.json` exposes the live `/api/v1/sms/*` routes owned by the
  mounted endpoint file, including `providers`, `test`, and `send-2fa-code`
- no live source imports of
  `backend/app/services/sms_providers_api_service.py` were found in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- `backend/app/services/sms_providers_api_service.py` differed from the
  mounted owner only by stale imports and typing drift and no longer owned
  runtime route behavior

Cleanup performed:
- removed `backend/app/services/sms_providers_api_service.py`

Effect:
- no mounted runtime route was removed
- live SMS provider route ownership remains unchanged
- one more dead router-style service residue is gone
