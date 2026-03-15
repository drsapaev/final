# AI Gateway API Service Cleanup

`backend/app/services/ai_gateway_api_service.py` was a detached router-style
residue for the mounted AI gateway endpoint owner.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/ai_gateway.py` with `prefix="/ai/v2"`
- `backend/openapi.json` exposes the live `/api/v1/ai/v2/*` routes owned by
  the mounted endpoint file
- no live source imports of `backend/app/services/ai_gateway_api_service.py`
  were found in `backend/app`, `backend/tests`, `docs`, or `frontend`
- `backend/app/services/ai_gateway_api_service.py` differed from the mounted
  owner only by typing and whitespace drift and no longer owned runtime route
  behavior

Cleanup performed:
- removed `backend/app/services/ai_gateway_api_service.py`

Effect:
- no mounted runtime route was removed
- live AI gateway route ownership remains unchanged
- one more dead router-style service residue is gone
