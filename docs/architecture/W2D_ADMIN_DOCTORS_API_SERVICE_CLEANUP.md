# Admin Doctors API Service Cleanup

`backend/app/services/admin_doctors_api_service.py` was a detached router-style
residue for the mounted admin doctors endpoint owner.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/admin_doctors.py` with `prefix="/admin"`
- `backend/openapi.json` exposes the live `/api/v1/admin/doctors*` routes owned
  by the mounted endpoint file
- no live source imports of `backend/app/services/admin_doctors_api_service.py`
  were found in `backend/app`, `backend/tests`, `docs`, or `frontend`
- `backend/app/services/admin_doctors_api_service.py` was not the mounted route
  owner and represented an unused alternate implementation for the same admin
  doctors surface

Cleanup performed:
- removed `backend/app/services/admin_doctors_api_service.py`

Effect:
- no mounted runtime route was removed
- live admin doctors route ownership remains unchanged
- one more dead router-style service residue is gone
