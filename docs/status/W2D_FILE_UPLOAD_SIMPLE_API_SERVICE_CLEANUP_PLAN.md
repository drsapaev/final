# File Upload Simple API Service Cleanup Plan

Scope:
- delete dead router-style duplicate
  `backend/app/services/file_upload_simple_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner
  `file_upload_simple.py`
- `backend/openapi.json` contains the live `/api/v1/files/upload-simple`
  route
- no confirmed backend, test, docs, or frontend import of
  `file_upload_simple_api_service.py` remains
- the service file duplicated mounted router logic instead of acting as a
  consumed service layer

Why this is safe:
- the file was not a mounted owner
- the live file upload simple endpoint remains in `file_upload_simple.py`
- removing the duplicate does not change the active file-upload runtime

Out of scope:
- changing file upload simple behavior
- removing the mounted `file_upload_simple.py` owner
