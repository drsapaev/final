# W2D 2FA Devices OpenAPI Parity Restoration Status

Status: completed

What changed:

- the published OpenAPI contract for shadowed `/api/v1/2fa/devices*` routes
  was aligned to the already-live runtime/front-end owner
- `two_factor_auth.py` now publishes the `GET` envelope and `DELETE` success
  schema used in runtime
- `two_factor_devices.py` keeps the shadowed `GET/DELETE` handlers for runtime
  continuity, but they are no longer published in OpenAPI
- `backend/openapi.json` was regenerated from the live application

Validation:

- `python generate_openapi.py --output openapi.json` succeeded
- `pytest tests/integration/test_two_factor_devices_endpoint_contract.py tests/integration/test_two_factor_devices_route_ownership_audit.py tests/test_openapi_contract.py -q`
  -> `19 passed`
- `python test_role_routing.py` -> deterministic RBAC matrix `19 passed`
- `pytest -q` -> `841 passed, 3 skipped`

Result:

- the `/api/v1/2fa/devices*` surface no longer has a published-contract drift
  against the live runtime/front-end contract
- no router reordering was needed
- protected residue handling is effectively exhausted for this lane
