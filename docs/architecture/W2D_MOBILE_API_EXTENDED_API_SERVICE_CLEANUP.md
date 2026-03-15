# Mobile API Extended API Service Cleanup

`backend/app/services/mobile_api_extended_api_service.py` was a detached
router-style residue for the mounted extended mobile endpoint owner.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/mobile_api_extended.py` with
  `prefix="/mobile"`
- `backend/openapi.json` exposes the live `/api/v1/mobile/*` routes owned by
  the mounted endpoint file, including auth, appointments, lab results,
  notifications, queues, profile, clinic info, and version routes
- no live source imports of
  `backend/app/services/mobile_api_extended_api_service.py` were found in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- `backend/app/services/mobile_api_extended_api_service.py` differed from the
  mounted owner only by stale import grouping, type-hint drift, and an unused
  `get_sms_manager` import and no longer owned runtime route behavior

Cleanup performed:
- removed `backend/app/services/mobile_api_extended_api_service.py`

Effect:
- no mounted runtime route was removed
- live extended mobile route ownership remains unchanged
- one more dead router-style service residue is gone
