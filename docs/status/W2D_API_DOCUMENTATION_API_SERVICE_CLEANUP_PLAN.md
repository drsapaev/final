## Scope

- candidate: `backend/app/services/api_documentation_api_service.py`
- mounted owner checked: `backend/app/api/v1/endpoints/api_documentation.py`
- route registration checked in `backend/app/api/v1/api.py`
- import/runtime review checked in `backend/app` and `backend/tests`

## Evidence

- `api.py` mounts `api_documentation.router` from the endpoint module, not from the service-side mirror
- no live source imports of `api_documentation_api_service.py` were found in `backend/app` or `backend/tests`
- service file duplicates endpoint-router content instead of owning runtime-only logic

## Planned change

- remove `api_documentation_api_service.py` as duplicate/unmounted residue
- keep mounted endpoint behavior unchanged
- run `pytest tests/test_openapi_contract.py -q`
- run `pytest -q`

## Out of scope

- any change to `/documentation/*` runtime behavior
- docs/product changes for API documentation endpoints
- broader cleanup outside this single duplicate mirror
