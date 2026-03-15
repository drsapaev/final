# Admin Stats API Service Cleanup

`backend/app/services/admin_stats_api_service.py` was a detached service-side
residue for the mounted admin stats endpoint owner.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/admin_stats.py` with `prefix="/admin"`
- `backend/openapi.json` exposes the live `/api/v1/admin/stats` route owned by
  the mounted endpoint file
- no live source imports of `backend/app/services/admin_stats_api_service.py`
  were found in `backend/app`, `backend/tests`, `docs`, or `frontend`
- `backend/app/services/admin_stats_api_service.py` was not the mounted route
  owner and represented an unused alternate implementation for the same admin
  stats surface

Cleanup performed:
- removed `backend/app/services/admin_stats_api_service.py`

Effect:
- no mounted runtime route was removed
- live admin stats route ownership remains unchanged
- one more dead service-side residue is gone
