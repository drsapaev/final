# W2D API Reference Settings and Notifications Verification Status

Status: completed

What changed:

- `docs/API_REFERENCE.md` was reframed as a curated reference
- the `Notifications` section now matches current OpenAPI paths and live schema
  shape for settings/history
- the `Settings` section now reflects the live response shape more explicitly

Validation:

- `pytest tests/test_openapi_contract.py -q` -> `14 passed`
- route and schema claims were checked against:
  - `backend/openapi.json`
  - `backend/app/api/v1/endpoints/notifications.py`
  - `backend/app/api/v1/endpoints/settings.py`

Result:

- the touched `API_REFERENCE.md` sections no longer advertise the removed
  `/notifications/settings/me` contract
- the file now more honestly describes itself as curated documentation rather
  than an exact route inventory
