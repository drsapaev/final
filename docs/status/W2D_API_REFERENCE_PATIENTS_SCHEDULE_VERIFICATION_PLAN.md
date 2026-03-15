# W2D API Reference Patients Schedule Verification Plan

Scope:

- verify the `Patients` section and add missing `Schedule` coverage in
  `docs/API_REFERENCE.md` against current OpenAPI and mounted owners
- keep the slice docs-only
- avoid turning the pass into a full patient-registry or scheduling-spec rewrite

Evidence targets:

- `backend/openapi.json`
- `backend/app/api/v1/api.py`
- `backend/app/api/v1/endpoints/patients.py`
- `backend/app/api/v1/endpoints/schedule.py`

Expected outcome:

- stale patient query naming corrected
- modern `/patients*` registry helpers reflected
- self-service patient portal reads kept distinct from the registry surface
- a new curated `/schedule*` section added
- schedule access notes documented conservatively from the live mounted owner
