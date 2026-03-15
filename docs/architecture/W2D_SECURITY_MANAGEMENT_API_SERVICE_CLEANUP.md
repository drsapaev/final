# Security Management API Service Cleanup

`backend/app/services/security_management_api_service.py` was a detached
router-style duplicate of the mounted security management endpoint owner.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/security_management.py` via
  `security_management_router`
- `backend/openapi.json` exposes the live `/api/v1/admin/security/*` surface
  from the mounted endpoint owner
- no live source imports of
  `backend/app/services/security_management_api_service.py` were found in
  `backend/app` or `backend/tests`
- `backend/app/services/security_management_api_service.py` duplicated the
  router logic already owned by
  `backend/app/api/v1/endpoints/security_management.py`

Cleanup performed:
- removed `backend/app/services/security_management_api_service.py`

Effect:
- no mounted runtime route was removed
- live `/api/v1/admin/security/*` ownership remains unchanged
- one more dead router-style service duplicate is gone
