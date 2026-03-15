# Clinic Management API Service Cleanup Plan

Scope:
- review detached `backend/app/services/clinic_management_api_service.py`
- if safe, merge any behavior-bearing parity into the mounted
  `backend/app/api/v1/endpoints/clinic_management.py` owner
- remove the detached duplicate only after targeted endpoint proof

Evidence:
- the live clinic routes are mounted from
  `backend/app/api/v1/endpoints/clinic_management.py`
- `backend/openapi.json` contains the published `/api/v1/clinic/*` contract
- no confirmed backend, test, docs, or frontend imports of the detached file
  remain
- the only meaningful drift is equipment branch-scope handling already backed
  by clinic CRUD/repository helpers

Why this is safe:
- the mounted owner stays the public router owner
- the ported logic is narrow and limited to equipment routes
- targeted endpoint tests protect both unscoped and scoped behavior before
  cleanup

Out of scope:
- changing branch, license, backup, or system-info behavior
- changing auth, payment, queue, or EMR domains
