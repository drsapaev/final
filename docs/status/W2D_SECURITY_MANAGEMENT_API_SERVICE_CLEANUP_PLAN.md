# Security Management API Service Cleanup Plan

Scope:
- delete dead router-style duplicate
  `backend/app/services/security_management_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner
  `security_management.py`
- `backend/openapi.json` contains the live `/api/v1/admin/security/*` routes
- no confirmed backend or test import of
  `security_management_api_service.py` remains
- the service file duplicated mounted router logic instead of acting as a
  consumed service layer

Why this is safe:
- the file was not a mounted owner
- the live security endpoints remain in `security_management.py`
- removing the duplicate does not change the active security runtime

Out of scope:
- changing security endpoint behavior
- changing confirmation security policies
- removing the mounted `security_management.py` owner
