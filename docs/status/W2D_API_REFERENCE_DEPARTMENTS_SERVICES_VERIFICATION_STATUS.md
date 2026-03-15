# W2D API Reference Departments Services Verification Status

Status: completed

What changed:

- the `Departments` section in `docs/API_REFERENCE.md` now reflects the live
  read-only `/departments`, `/departments/active`, and
  `/departments/{department_id}` surface
- stale departments create/update claims were removed
- the `Services` section now reflects the live catalog CRUD, category
  management, and helper-route shape
- the stale `/services/department/{dept_id}` claim was removed
- access notes were downgraded where current published OpenAPI does not expose
  a security block for the reviewed services routes

Validation:

- `pytest tests/test_openapi_contract.py -q` -> `14 passed`
- route and schema claims were checked against:
  - `backend/openapi.json`
  - `backend/app/api/v1/endpoints/departments.py`
  - `backend/app/api/v1/endpoints/services.py`

Result:

- the touched docs no longer advertise non-existent department CRUD
- the touched docs no longer describe the services surface as the old narrow
  department-filter listing
- the section pair now better matches the published contract while remaining a
  curated high-level reference
