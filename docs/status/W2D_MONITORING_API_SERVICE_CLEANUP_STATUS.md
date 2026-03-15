## Result

`backend/app/services/monitoring_api_service.py` was removed as duplicate/unmounted residue.

## Runtime impact

- no route registration changed
- no mounted runtime behavior changed
- endpoint-side `monitoring.py` remains untouched for a later review-first cleanup decision

## Validation

- `pytest tests/test_openapi_contract.py -q`
- `pytest -q`
