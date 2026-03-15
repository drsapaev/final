# Admin Doctors API Service Cleanup Plan

Scope:
- delete dead router-style residue
  `backend/app/services/admin_doctors_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner `admin_doctors.py`
- `backend/openapi.json` contains the live `/api/v1/admin/doctors*` routes
  served by that owner
- no confirmed backend, test, docs, or frontend import of
  `admin_doctors_api_service.py` remains
- the file was not the mounted owner and represented an unused alternate
  implementation for the same admin doctors surface

Why this is safe:
- the file was not a mounted owner
- the live admin doctors endpoints remain in `admin_doctors.py`
- removing the residue does not change the active admin doctors runtime

Out of scope:
- changing admin doctors behavior
- changing schedule or specialty logic
- removing the mounted `admin_doctors.py` owner
