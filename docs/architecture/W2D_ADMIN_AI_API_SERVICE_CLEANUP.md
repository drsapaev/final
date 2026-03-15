# Admin AI API Service Cleanup

`backend/app/services/admin_ai_api_service.py` was a detached router-style
residue for the mounted admin AI endpoint owner.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/admin_ai.py` with `prefix="/admin"`
- `backend/openapi.json` exposes the live `/api/v1/admin/ai/*` routes owned by
  the mounted endpoint file
- no live source imports of `backend/app/services/admin_ai_api_service.py`
  were found in `backend/app`, `backend/tests`, `docs`, or `frontend`
- `backend/app/services/admin_ai_api_service.py` still contained a detached
  router implementation for the same admin AI surface and was no longer the
  runtime route owner

Cleanup performed:
- removed `backend/app/services/admin_ai_api_service.py`

Effect:
- no mounted runtime route was removed
- live admin AI route ownership remains unchanged
- one more dead router-style service residue is gone
