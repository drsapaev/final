# File Upload Simple API Service Cleanup

`backend/app/services/file_upload_simple_api_service.py` was a detached
router-style duplicate of the mounted file-upload-simple endpoint owner.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/file_upload_simple.py`
- `backend/openapi.json` exposes the live `/api/v1/files/upload-simple` route
  from the mounted endpoint owner
- no live source imports of
  `backend/app/services/file_upload_simple_api_service.py` were found in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- `backend/app/services/file_upload_simple_api_service.py` duplicated the
  router logic already owned by
  `backend/app/api/v1/endpoints/file_upload_simple.py`

Cleanup performed:
- removed `backend/app/services/file_upload_simple_api_service.py`

Effect:
- no mounted runtime route was removed
- live file-upload-simple route ownership remains unchanged
- one more dead router-style service duplicate is gone
