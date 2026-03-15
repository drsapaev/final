# Medical Equipment API Service Cleanup Plan

Scope:
- delete dead router-style duplicate
  `backend/app/services/medical_equipment_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner
  `medical_equipment.py`
- `backend/openapi.json` contains the live `/api/v1/medical-equipment/*`
  routes served by that owner
- no confirmed backend, test, docs, or frontend import of
  `medical_equipment_api_service.py` remains
- the service file duplicated mounted router logic instead of acting as a
  consumed service layer

Why this is safe:
- the file was not a mounted owner
- the live medical-equipment endpoints remain in `medical_equipment.py`
- removing the duplicate does not change the active medical-equipment runtime

Out of scope:
- changing medical-equipment behavior
- changing device-role gates
- removing the mounted `medical_equipment.py` owner
