## Scope

- candidate: `backend/app/services/monitoring_api_service.py`
- endpoint counterpart checked: `backend/app/api/v1/endpoints/monitoring.py`
- route registration checked in `backend/app/api/v1/api.py`
- import/runtime review checked in `backend/app` and `backend/tests`

## Evidence

- no `monitoring.router` registration was found in `backend/app/api/v1/api.py`
- no live source imports of `monitoring_api_service.py` were found in `backend/app` or `backend/tests`
- the service file duplicated monitoring endpoint content instead of owning unique runtime logic

## Planned change

- remove `monitoring_api_service.py` as duplicate/unmounted residue
- keep the endpoint-side file untouched in this slice
- run `pytest tests/test_openapi_contract.py -q`
- run `pytest -q`

## Out of scope

- cleanup of `backend/app/api/v1/endpoints/monitoring.py`
- broader observability/monitoring deprecation decisions
- any mounted route behavior changes
