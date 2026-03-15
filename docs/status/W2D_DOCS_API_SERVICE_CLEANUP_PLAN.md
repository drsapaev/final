## Scope

- candidate: `backend/app/services/docs_api_service.py`
- mounted owner checked: `backend/app/api/v1/endpoints/docs.py`
- route registration checked in `backend/app/api/v1/api.py`
- import/runtime review checked in `backend/app` and `backend/tests`

## Evidence

- `api.py` mounts `docs.router` from the endpoint module, not from the service-side mirror
- no live source imports of `docs_api_service.py` were found in `backend/app` or `backend/tests`
- the service file duplicates endpoint-router content instead of owning runtime-only logic

## Planned change

- remove `docs_api_service.py` as duplicate/unmounted residue
- keep mounted `/docs/*`-adjacent behavior unchanged
- run `pytest tests/test_openapi_contract.py -q`
- run `pytest -q`

## Out of scope

- any change to mounted documentation routes
- broader documentation-domain cleanup
- cleanup of other service-side mirrors in the same slice
