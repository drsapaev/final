# Backup Management Endpoint Cleanup

`backend/app/api/v1/endpoints/backup_management.py` and
`backend/app/services/backup_management_api_service.py` were detached legacy
entrypoint artifacts.

Verified facts:
- `backend/app/api/v1/api.py` did not include `backup_management.router`
- `backend/app/api/v1/api.py` mounted `system_management.router` under
  `/system`, and `backend/openapi.json` exposed the live backup surface under
  `/api/v1/system/backup/*`
- no live source imports of
  `backend/app/api/v1/endpoints/backup_management.py` or
  `backend/app/services/backup_management_api_service.py` were found in
  `backend/app` or `backend/tests`
- `clinic_management.py` imports the `backup_management` service object from
  `clinic_management_service`, not the detached endpoint module
- `backend/PRODUCTION_READINESS_REPORT.md` still pointed to the dead endpoint
  file and was corrected to the mounted `system_management.py` owner

Cleanup performed:
- removed `backend/app/api/v1/endpoints/backup_management.py`
- removed `backend/app/services/backup_management_api_service.py`
- corrected the stale backup API file reference in
  `backend/PRODUCTION_READINESS_REPORT.md`

Effect:
- no mounted runtime route was removed
- live `/api/v1/system/backup/*` ownership remains unchanged
- dead backup entrypoint residue and one stale docs reference are gone
