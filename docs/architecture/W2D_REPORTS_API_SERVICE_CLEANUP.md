# Reports API Service Cleanup

`backend/app/services/reports_api_service.py` was a detached router-style
residue for the mounted reports endpoint owner.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/reports.py` with `prefix="/reports"`
- `backend/openapi.json` exposes the live `/api/v1/reports/*` routes owned by
  the mounted endpoint file, including `patient`, `appointments`, `financial`,
  `daily-summary`, `available-reports`, `cleanup`, and `files`
- no live source imports of `backend/app/services/reports_api_service.py` were
  found in `backend/app`, `backend/tests`, `docs`, or `frontend`
- `backend/app/services/reports_api_service.py` differed from the mounted owner
  only by stale imports and typing drift and no longer owned runtime route
  behavior

Cleanup performed:
- removed `backend/app/services/reports_api_service.py`

Effect:
- no mounted runtime route was removed
- live reports route ownership remains unchanged
- one more dead router-style service residue is gone
