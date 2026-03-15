# W2D API Reference Patients Schedule Verification Status

Status: completed

What changed:

- the `Patients` section in `docs/API_REFERENCE.md` now reflects the broader
  live `/patients*` registry surface instead of the old mini-summary
- stale `search` query naming was replaced with the live `q` plus `phone`
  split
- missing patient registry helpers were added to the curated map
- a new `Schedule` section now documents the live `/schedule*` helper surface
- schedule access notes were narrowed to match the live mounted owner

Validation:

- `pytest tests/test_openapi_contract.py -q` -> `14 passed`
- route and schema claims were checked against:
  - `backend/openapi.json`
  - `backend/app/api/v1/api.py`
  - `backend/app/api/v1/endpoints/patients.py`
  - `backend/app/api/v1/endpoints/schedule.py`

Result:

- the touched docs no longer underspecify the live `/patients*` registry
  surface
- the file now contains a direct curated section for the live `/schedule*`
  owner it already references elsewhere
- the reviewed sections better match the published contract while remaining a
  curated high-level reference
