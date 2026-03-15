## Result

`backend/app/services/health_api_service.py` was removed as duplicate/unmounted residue.

## Runtime impact

- no route registration changed
- no mounted endpoint behavior changed
- health-check runtime remains owned by `backend/app/api/v1/endpoints/health.py`

## Validation

- `pytest tests/test_openapi_contract.py -q`
- `pytest -q`
