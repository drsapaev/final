## Scope

- candidate: `backend/app/services/health_api_service.py`
- mounted owner checked: `backend/app/api/v1/endpoints/health.py`
- route registration checked in `backend/app/api/v1/api.py`
- import/runtime review checked in `backend/app` and `backend/tests`

## Evidence

- `api.py` mounts `health_ep.router` from the endpoint module, not from the service-side mirror
- no live source imports of `health_api_service.py` were found in `backend/app` or `backend/tests`
- the service file duplicates mounted endpoint content instead of owning unique runtime logic

## Planned change

- remove `health_api_service.py` as duplicate/unmounted residue
- keep mounted `/health` and `/status` behavior unchanged
- run `pytest tests/test_openapi_contract.py -q`
- run `pytest -q`

## Out of scope

- any health endpoint behavior changes
- broader observability or monitoring cleanup
- cleanup of any other service-side mirror in this slice
