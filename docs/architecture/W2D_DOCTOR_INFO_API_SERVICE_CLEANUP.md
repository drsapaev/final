# Doctor Info API Service Cleanup

`backend/app/services/doctor_info_api_service.py` was a detached
router-style duplicate of the mounted doctor info endpoint owner.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/doctor_info.py` with
  `prefix="/doctor-info"`
- `backend/openapi.json` exposes the live
  `/api/v1/doctor-info/doctors/{doctor_id}`,
  `/api/v1/doctor-info/doctors`,
  `/api/v1/doctor-info/doctors/by-user/{user_id}`,
  `/api/v1/doctor-info/departments/{department_id}`,
  `/api/v1/doctor-info/departments`,
  `/api/v1/doctor-info/appointments/{appointment_id}/doctor-info`,
  `/api/v1/doctor-info/doctors/{doctor_id}/formatted-info`, and
  `/api/v1/doctor-info/departments/{department_id}/formatted-info` routes owned
  by the mounted endpoint file
- no live source imports of
  `backend/app/services/doctor_info_api_service.py` were found in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- `backend/app/services/doctor_info_api_service.py` duplicated the router
  logic already owned by
  `backend/app/api/v1/endpoints/doctor_info.py`, with only typing/import drift

Cleanup performed:
- removed `backend/app/services/doctor_info_api_service.py`

Effect:
- no mounted runtime route was removed
- live doctor-info route ownership remains unchanged
- one more dead router-style service duplicate is gone
