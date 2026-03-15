# Doctor Info API Service Cleanup Plan

Scope:
- delete dead router-style duplicate
  `backend/app/services/doctor_info_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner `doctor_info.py`
- `backend/openapi.json` contains the live `/api/v1/doctor-info/*` routes
  served by that owner
- no confirmed backend, test, docs, or frontend import of
  `doctor_info_api_service.py` remains
- the service file duplicated mounted router logic instead of acting as a
  consumed service layer

Why this is safe:
- the file was not a mounted owner
- the live doctor-info endpoints remain in `doctor_info.py`
- removing the duplicate does not change the active doctor-info runtime

Out of scope:
- changing doctor-info behavior
- changing doctor-info auth gates
- removing the mounted `doctor_info.py` owner
