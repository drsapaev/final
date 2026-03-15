# File System Simple Shim Cleanup

`backend/app/api/v1/endpoints/file_system_simple.py` and
`backend/app/services/file_system_simple_api_service.py` formed a detached
legacy shim pair.

Verified facts:
- `backend/app/api/v1/api.py` mounts `file_system.router`,
  `file_upload_simple.router`, `file_upload_json.router`, and
  `file_test.router`, but does not mount `file_system_simple.router`
- no live source imports of `file_system_simple.py` or
  `file_system_simple_api_service.py` were found in `backend/app` or
  `backend/tests`
- the endpoint and service files were byte-identical stub implementations

Cleanup performed:
- removed `backend/app/api/v1/endpoints/file_system_simple.py`
- removed `backend/app/services/file_system_simple_api_service.py`

Effect:
- no runtime route was removed, because the shim endpoint was never mounted
- no live service owner changed, because the service shim had no runtime
  imports
- the mounted file-system surface remains owned by the non-simple `/files`
  routers already registered in `backend/app/api/v1/api.py`
