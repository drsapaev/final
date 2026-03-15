# Backup Management Endpoint Cleanup Plan

Scope:
- delete dead endpoint artifact
  `backend/app/api/v1/endpoints/backup_management.py`
- delete detached router duplicate
  `backend/app/services/backup_management_api_service.py`
- correct stale docs that still pointed at the dead endpoint file

Evidence:
- `backend/app/api/v1/api.py` does not mount `backup_management.router`
- `backend/openapi.json` contains the mounted backup surface under
  `/api/v1/system/backup/*`
- no confirmed backend or test import of the endpoint module remains
- no confirmed live import of `backup_management_api_service.py` remains
- `clinic_management.py` uses the service object from
  `clinic_management_service`, not the endpoint module

Why this is safe:
- the endpoint file was not mounted, so deleting it cannot change runtime
  routing
- the duplicate router file under `services/` had no confirmed live imports
- the mounted `system_management.py` owner remains intact

Out of scope:
- changing the live `/system/backup/*` API behavior
- refactoring `clinic_management_service`
- backup retention or restore semantics
