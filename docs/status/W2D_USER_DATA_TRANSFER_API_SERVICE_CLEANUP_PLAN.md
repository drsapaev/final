# User Data Transfer API Service Cleanup Plan

Scope:
- delete dead router-style residue
  `backend/app/services/user_data_transfer_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner
  `user_data_transfer.py`
- `backend/openapi.json` contains the live `/api/v1/admin/user-data/*` routes
  served by that owner
- no confirmed backend, test, docs, or frontend import of
  `user_data_transfer_api_service.py` remains
- the file was not the mounted owner and represented an older detached router
  implementation for the same user data transfer surface

Why this is safe:
- the file was not a mounted owner
- the live user data transfer endpoints remain in `user_data_transfer.py`
- removing the residue does not change the active user data transfer runtime

Out of scope:
- changing user data transfer behavior
- changing transfer validation or confirmation behavior
- removing the mounted `user_data_transfer.py` owner
