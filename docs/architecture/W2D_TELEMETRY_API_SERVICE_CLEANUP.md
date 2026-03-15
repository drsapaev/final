# Telemetry API Service Cleanup

`backend/app/services/telemetry_api_service.py` was a detached router-style
duplicate of the mounted telemetry endpoint owner.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/telemetry.py`
- `backend/openapi.json` exposes the live `/api/v1/telemetry` and
  `/api/v1/telemetry/status` routes owned by the mounted endpoint file
- no live source imports of `backend/app/services/telemetry_api_service.py`
  were found in `backend/app`, `backend/tests`, `docs`, or `frontend`
- `backend/app/services/telemetry_api_service.py` duplicated the router logic
  already owned by `backend/app/api/v1/endpoints/telemetry.py`, with only
  typing/import drift and formatting drift

Cleanup performed:
- removed `backend/app/services/telemetry_api_service.py`

Effect:
- no mounted runtime route was removed
- live telemetry route ownership remains unchanged
- one more dead router-style service duplicate is gone
