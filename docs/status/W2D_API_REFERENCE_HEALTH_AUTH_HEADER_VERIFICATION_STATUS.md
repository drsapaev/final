# W2D API Reference Health Auth Header Verification Status

Status: completed

What changed:

- the `Health` section in `docs/API_REFERENCE.md` now reflects the live
  `/health` plus `/status` owner shape instead of the old root `/` claim
- adjacent public and authenticated health-style route families are now called
  out explicitly
- the `Authentication Header` section now reflects the current published
  `OAuth2PasswordBearer` scheme and password-flow token URL
- the docs now explicitly note that not every route in the reference is
  protected

Validation:

- `pytest tests/test_openapi_contract.py -q` -> `14 passed`
- route and scheme claims were checked against:
  - `backend/openapi.json`
  - `backend/app/api/v1/api.py`
  - `backend/app/api/v1/endpoints/health.py`

Result:

- the touched footer sections no longer mix non-API root claims into the
  `/api/v1` reference
- the auth-header guidance is now tied to the published security scheme instead
  of a context-free generic sentence
- the reviewed sections better match the published contract while remaining a
  curated high-level reference
