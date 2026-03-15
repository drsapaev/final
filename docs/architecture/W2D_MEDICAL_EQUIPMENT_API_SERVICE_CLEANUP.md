# Medical Equipment API Service Cleanup

`backend/app/services/medical_equipment_api_service.py` was a detached
router-style duplicate of the mounted medical equipment endpoint owner.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/medical_equipment.py` with
  `prefix="/medical-equipment"`
- `backend/openapi.json` exposes the live
  `/api/v1/medical-equipment/devices`,
  `/api/v1/medical-equipment/devices/{device_id}`,
  `/api/v1/medical-equipment/devices/type/{device_type}`,
  `/api/v1/medical-equipment/devices/{device_id}/connect`,
  `/api/v1/medical-equipment/devices/{device_id}/disconnect`,
  `/api/v1/medical-equipment/devices/{device_id}/status`,
  `/api/v1/medical-equipment/measurements`,
  `/api/v1/medical-equipment/devices/{device_id}/calibrate`,
  `/api/v1/medical-equipment/devices/{device_id}/diagnostics`,
  `/api/v1/medical-equipment/devices/{device_id}/config`,
  `/api/v1/medical-equipment/devices/{device_id}/statistics`,
  `/api/v1/medical-equipment/statistics/overview`,
  `/api/v1/medical-equipment/measurements/export`,
  `/api/v1/medical-equipment/quick-measurement/{device_type}`,
  `/api/v1/medical-equipment/device-types`, and
  `/api/v1/medical-equipment/connection-types` routes owned by the mounted
  endpoint file
- no live source imports of
  `backend/app/services/medical_equipment_api_service.py` were found in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- `backend/app/services/medical_equipment_api_service.py` duplicated the router
  logic already owned by
  `backend/app/api/v1/endpoints/medical_equipment.py`, with only typing/import
  drift

Cleanup performed:
- removed `backend/app/services/medical_equipment_api_service.py`

Effect:
- no mounted runtime route was removed
- live medical-equipment route ownership remains unchanged
- one more dead router-style service duplicate is gone
