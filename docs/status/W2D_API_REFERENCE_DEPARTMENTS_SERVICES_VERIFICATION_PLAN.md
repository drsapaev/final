# W2D API Reference Departments Services Verification Plan

Scope:

- verify the adjacent `Departments` and `Services` sections in
  `docs/API_REFERENCE.md` against current OpenAPI and mounted owners
- keep the slice docs-only
- avoid turning the pass into a full clinic-catalog specification rewrite

Evidence targets:

- `backend/openapi.json`
- `backend/app/api/v1/endpoints/departments.py`
- `backend/app/api/v1/endpoints/services.py`

Expected outcome:

- stale departments CRUD claims deleted
- current department read-only lookup routes reflected
- stale `/services/department/{dept_id}` claim deleted
- current services catalog/category/helper route families reflected
- access notes downgraded where published OpenAPI is looser than the old docs
