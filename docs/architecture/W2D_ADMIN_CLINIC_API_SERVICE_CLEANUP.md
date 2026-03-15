# Admin Clinic API Service Cleanup

`backend/app/services/admin_clinic_api_service.py` was a detached router-style
residue for the mounted admin clinic endpoint owner.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/admin_clinic.py` with `prefix="/admin"`
- `backend/openapi.json` exposes the live `/api/v1/admin/clinic/*` routes
  owned by the mounted endpoint file, including clinic settings and clinic
  logo routes
- no live backend, test, or frontend imports of
  `backend/app/services/admin_clinic_api_service.py` remained
- remaining docs references were stale architecture notes and were updated to
  point only at the mounted endpoint owner
- `backend/app/services/admin_clinic_api_service.py` differed from the mounted
  owner only by stale imports and typing drift and no longer owned runtime
  route behavior

Cleanup performed:
- removed `backend/app/services/admin_clinic_api_service.py`
- removed stale doc references from board-state architecture notes

Effect:
- no mounted runtime route was removed
- live admin clinic route ownership remains unchanged
- one more dead router-style service residue is gone
