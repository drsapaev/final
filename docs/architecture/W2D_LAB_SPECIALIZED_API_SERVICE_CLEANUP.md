# Lab Specialized API Service Cleanup

`backend/app/services/lab_specialized_api_service.py` was a detached
router-style duplicate of the mounted lab specialized endpoint owner.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/lab_specialized.py`
- `backend/openapi.json` exposes the live `/api/v1/lab/tests`,
  `/api/v1/lab/results`, `/api/v1/lab/reports`,
  `/api/v1/lab/reference-ranges`, and `/api/v1/lab/equipment` routes owned by
  the mounted endpoint file
- no live source imports of
  `backend/app/services/lab_specialized_api_service.py` were found in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- `backend/app/services/lab_specialized_api_service.py` duplicated the router
  logic already owned by `backend/app/api/v1/endpoints/lab_specialized.py`,
  with only typing-annotation drift

Cleanup performed:
- removed `backend/app/services/lab_specialized_api_service.py`

Effect:
- no mounted runtime route was removed
- live lab specialized route ownership remains unchanged
- one more dead router-style service duplicate is gone
