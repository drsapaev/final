# Monitoring Endpoint Cleanup

`backend/app/api/v1/endpoints/monitoring.py` was a dead endpoint artifact.

Verified facts:
- it defined `router = APIRouter(prefix="/monitoring", tags=["monitoring"])`
- `backend/app/api/v1/api.py` did not include `monitoring.router`
- live frontend/admin monitoring calls already target `/system/monitoring/*`
- the stale user-facing docs still referenced `/admin/monitoring/*`

Cleanup performed:
- removed `backend/app/api/v1/endpoints/monitoring.py`
- updated `docs/API_REFERENCE.md` to point to the mounted `/system/monitoring/*` surface

Effect:
- no runtime route was removed, because the endpoint was never mounted
- one more dead endpoint artifact is gone
- docs now align with the actual monitoring surface
