## Result

`backend/app/services/api_documentation_api_service.py` was removed as duplicate/unmounted residue.

## Runtime impact

- no route registration changed
- no mounted endpoint behavior changed
- `/documentation/*` remains owned by `backend/app/api/v1/endpoints/api_documentation.py`

## Validation

- `pytest tests/test_openapi_contract.py -q`
- `pytest -q`
