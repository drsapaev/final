# W2D API Reference Authentication and Users Verification Status

Status: completed

What changed:

- `docs/API_REFERENCE.md` now documents the live split between `/auth/*` and
  `/authentication/*`
- the `refresh` and `logout` request shapes now match current OpenAPI
- the `Users` section now points to `/auth/me`, `/users/me/preferences`, and
  the current `/users/users*` management surface instead of the removed
  `/users/me` route

Validation:

- `pytest tests/test_openapi_contract.py -q` -> `14 passed`
- route and schema claims were checked against:
  - `backend/openapi.json`
  - `backend/app/api/v1/endpoints/auth.py`
  - `backend/app/api/v1/endpoints/authentication.py`
  - `backend/app/api/v1/endpoints/user_management.py`

Result:

- the touched `API_REFERENCE.md` sections no longer advertise the removed
  `/users/me` contract
- the auth section no longer describes the refresh flow with a stale header
  pattern
