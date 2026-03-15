# File System Simple Shim Cleanup Plan

Scope:
- delete dead endpoint artifact `backend/app/api/v1/endpoints/file_system_simple.py`
- delete duplicate dead mirror `backend/app/services/file_system_simple_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` does not mount `file_system_simple.router`
- mounted `/files` behavior already belongs to `file_system`, `file_upload_simple`,
  `file_upload_json`, and `file_test`
- no confirmed frontend, backend runtime, or test imports of the shim pair remain
- the endpoint and service files are byte-identical stub implementations

Why this is safe:
- the endpoint was not mounted, so deleting it cannot change runtime routing
- the service file had no live imports, so deleting it cannot change mounted
  runtime behavior

Out of scope:
- redesign of the mounted file-system APIs
- cleanup of live `/files` endpoints
- storage behavior changes
