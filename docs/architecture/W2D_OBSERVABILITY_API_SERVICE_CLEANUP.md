# Observability API Service Cleanup

`backend/app/services/observability_api_service.py` was a detached
router-style duplicate of the mounted observability endpoint owner.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/observability.py`
- `backend/openapi.json` exposes the live `/api/v1/observability/*` surface
  from the mounted endpoint owner
- no live source imports of
  `backend/app/services/observability_api_service.py` were found in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- `backend/app/services/observability_api_service.py` was byte-identical to
  `backend/app/api/v1/endpoints/observability.py`

Cleanup performed:
- removed `backend/app/services/observability_api_service.py`

Effect:
- no mounted runtime route was removed
- live `/api/v1/observability/*` ownership remains unchanged
- one more dead router-style service duplicate is gone
