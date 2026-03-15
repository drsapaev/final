# W2D 2FA Devices OpenAPI Parity Restoration Plan

Scope:

- keep the existing runtime owner split for `/api/v1/2fa/devices*`
- align published OpenAPI to the live runtime/front-end contract for the
  shadowed `GET` and `DELETE` routes
- avoid router reordering or any rewrite of 2FA flow behavior

Implementation targets:

- publish `GET /api/v1/2fa/devices` from
  `backend/app/api/v1/endpoints/two_factor_auth.py`
- publish `DELETE /api/v1/2fa/devices/{device_id}` from
  `backend/app/api/v1/endpoints/two_factor_auth.py`
- hide the shadowed `GET/DELETE` duplicates in
  `backend/app/api/v1/endpoints/two_factor_devices.py`
- regenerate `backend/openapi.json`

Expected outcome:

- runtime owner unchanged
- frontend expectations unchanged
- no more OpenAPI/runtime mismatch for the shadowed 2FA device operations
