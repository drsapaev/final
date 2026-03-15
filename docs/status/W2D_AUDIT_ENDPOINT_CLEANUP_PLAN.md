# Audit Endpoint Cleanup Plan

Scope:
- delete dead endpoint artifact `backend/app/api/v1/endpoints/audit.py`
- delete detached router duplicate `backend/app/services/audit_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` does not mount `audit.router`
- `backend/openapi.json` does not contain `/api/v1/audit*`
- no confirmed backend or test import of the endpoint module remains
- no confirmed live import of `audit_api_service.py` remains
- no confirmed frontend or docs usage of the route surface remains

Why this is safe:
- the endpoint file was not mounted, so deleting it cannot change runtime
  routing
- the duplicate router file under `services/` had no confirmed live imports
- the audit CRUD layer remains untouched

Out of scope:
- changing audit logging behavior
- adding a new mounted audit API owner
- removing audit storage or CRUD code
