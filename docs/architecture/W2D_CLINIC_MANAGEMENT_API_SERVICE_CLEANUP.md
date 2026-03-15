# Clinic Management API Service Cleanup

`backend/app/services/clinic_management_api_service.py` was not a safe blind
delete candidate at the start of review because it carried newer
request-branch-scope wiring for clinic equipment routes than the mounted owner
in `backend/app/api/v1/endpoints/clinic_management.py`.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/clinic_management.py` at `/api/v1/clinic`
- `backend/openapi.json` publishes the live `/api/v1/clinic/*` routes
- no live imports of `clinic_management_api_service.py` remained in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- the behavior-bearing delta was limited to equipment endpoints:
  request-scoped branch handling and `BranchScope*` error mapping
- branch-scope CRUD primitives already existed and were covered in
  `backend/tests/unit/test_clinic_management_equipment_scoped_crud.py`

Cleanup performed:
- ported the equipment branch-scope helper and error mapping into the mounted
  `clinic_management.py` owner
- added endpoint-contract coverage for unscoped admin behavior plus scoped
  filtering/blocking on `/api/v1/clinic/equipment`
- removed detached `backend/app/services/clinic_management_api_service.py`

Effect:
- no mounted `/api/v1/clinic/*` route was removed
- unscoped admin equipment listing still works
- scoped equipment requests now follow the same branch-scope path that the
  detached duplicate had already introduced
- one more mixed-risk residue is resolved without crossing protected domains
