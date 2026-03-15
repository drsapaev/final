# Admin Clinic API Service Cleanup Plan

Scope:
- delete dead router-style residue
  `backend/app/services/admin_clinic_api_service.py`
- remove stale docs references that still named the deleted duplicate

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner `admin_clinic.py`
- `backend/openapi.json` contains the live `/api/v1/admin/clinic/*` routes
  served by that owner
- no confirmed backend, test, or frontend import of
  `admin_clinic_api_service.py` remains
- the only remaining references were stale architecture notes, not runtime
  owners

Why this is safe:
- the file was not a mounted owner
- the live admin clinic endpoints remain in `admin_clinic.py`
- removing the residue does not change the active admin clinic runtime

Out of scope:
- changing clinic settings behavior
- changing clinic logo upload behavior
- removing the mounted `admin_clinic.py` owner
