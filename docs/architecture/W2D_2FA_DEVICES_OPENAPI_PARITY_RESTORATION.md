# W2D 2FA Devices OpenAPI Parity Restoration

## Summary

The mixed `/api/v1/2fa/devices*` ownership tail was resolved through a narrow
published-contract alignment pass.

This slice did not reorder routers or rewrite live 2FA runtime behavior.
Instead, it made the published OpenAPI contract match the runtime/front-end
contract that already existed.

## What changed

### Published GET owner aligned to runtime

- `backend/app/api/v1/endpoints/two_factor_auth.py` now publishes
  `GET /api/v1/2fa/devices` with the live
  `TwoFactorDeviceListResponse` envelope
- `backend/app/api/v1/endpoints/two_factor_devices.py` keeps its shadowed
  `GET /devices` route for runtime continuity, but it is now hidden from the
  published schema

### Published DELETE owner aligned to runtime

- `backend/app/api/v1/endpoints/two_factor_auth.py` now publishes
  `DELETE /api/v1/2fa/devices/{device_id}` with the live
  `TwoFactorSuccessResponse` schema
- `backend/app/api/v1/endpoints/two_factor_devices.py` keeps its shadowed
  `DELETE /devices/{device_id}` route for runtime continuity, but it is now
  hidden from the published schema

### Runtime ownership intentionally unchanged

- runtime first-match still resolves the shadowed `GET` and `DELETE` routes to
  `two_factor_auth.py`
- the remaining unique device-management routes continue to be owned and
  published from `two_factor_devices.py`
- frontend 2FA device screens remain aligned without code changes

## Proof

- `backend/tests/integration/test_two_factor_devices_endpoint_contract.py`
  still proves the live runtime payload shape consumed by the frontend
- `backend/tests/integration/test_two_factor_devices_route_ownership_audit.py`
  now proves that:
  - runtime first-match remains on `two_factor_auth.py`
  - published OpenAPI now reflects the auth-owner schema for the shadowed
    `GET/DELETE` operations
- `backend/generate_openapi.py` regenerated `backend/openapi.json`

## Decision

The protected 2FA device tail is no longer an active migration/parity blocker.

Current SSOT for `/api/v1/2fa/devices*`:

- shadowed `GET/DELETE` contract: `two_factor_auth.py`
- unique device-management routes: `two_factor_devices.py`
- published OpenAPI: aligned to that split runtime ownership

This remains a live architecture choice, but it is no longer a frontend/runtime
contract mismatch.

## Recommended next step

Shift away from protected residue handling and into docs/status consolidation,
while leaving `cashier_api_service.py` as a separate payment-critical review
surface outside the W2D cleanup lane.
