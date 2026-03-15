# Utils API Service Cleanup

`backend/app/services/utils_api_service.py` was a detached router-style residue
for the mounted utils endpoint owner.

Verified facts:
- `backend/app/api/v1/api.py` mounts `backend/app/api/v1/endpoints/utils.py`
  with `prefix="/utils"`
- `backend/openapi.json` exposes the live `/api/v1/utils/link-preview` route
  owned by the mounted endpoint file
- no live source imports of `backend/app/services/utils_api_service.py` were
  found in `backend/app`, `backend/tests`, `docs`, or `frontend`
- `backend/app/services/utils_api_service.py` differed from the mounted owner
  only by import ordering and whitespace drift and no longer owned runtime
  route behavior

Cleanup performed:
- removed `backend/app/services/utils_api_service.py`

Effect:
- no mounted runtime route was removed
- live utils route ownership remains unchanged
- one more dead router-style service residue is gone
