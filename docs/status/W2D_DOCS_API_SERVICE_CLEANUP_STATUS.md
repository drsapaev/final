## Result

`backend/app/services/docs_api_service.py` was removed as duplicate/unmounted residue.

## Runtime impact

- no route registration changed
- no mounted endpoint behavior changed
- documentation runtime remains owned by `backend/app/api/v1/endpoints/docs.py`

## Validation

- `pytest tests/test_openapi_contract.py -q`
- `pytest -q`
