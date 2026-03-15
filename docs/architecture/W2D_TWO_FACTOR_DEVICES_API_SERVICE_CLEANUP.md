# Two Factor Devices API Service Cleanup

`backend/app/services/two_factor_devices_api_service.py` and
`backend/app/repositories/two_factor_devices_api_repository.py` were handled as
a protected auth-adjacent duplicate pair, not as a blind-delete candidate.

Verified facts:
- `backend/app/api/v1/api.py` mounts both
  `backend/app/api/v1/endpoints/two_factor_auth.py` and
  `backend/app/api/v1/endpoints/two_factor_devices.py` under `/api/v1/2fa`
- `backend/openapi.json` publishes the device-management surface:
  - `/api/v1/2fa/devices`
  - `/api/v1/2fa/devices/{device_id}`
  - `/api/v1/2fa/devices/{device_id}/name`
  - `/api/v1/2fa/devices/{device_id}/sessions`
  - `/api/v1/2fa/devices/revoke-all`
  - `/api/v1/2fa/devices/statistics`
  - `/api/v1/2fa/devices/{device_id}/trust`
  - `/api/v1/2fa/devices/{device_id}/security-check`
- live frontend device usage remains in:
  - `frontend/src/components/TwoFactorSettings.jsx`
  - `frontend/src/components/security/TwoFactorManager.jsx`
- no live imports of the detached service or repository remained in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- diff vs the mounted owner was limited to typing/name drift plus an unused
  local variable
- runtime route introspection confirmed that `GET /api/v1/2fa/devices` and
  `DELETE /api/v1/2fa/devices/{device_id}` still resolve first to hidden
  handlers in `two_factor_auth.py`, while the remaining device-management
  routes are owned by `two_factor_devices.py`

Cleanup performed:
- added `backend/tests/integration/test_two_factor_devices_endpoint_contract.py`
  to protect:
  - the current frontend-facing runtime contract for shadowed
    `GET/DELETE /api/v1/2fa/devices*`
  - the unique mounted routes still owned by
    `backend/app/api/v1/endpoints/two_factor_devices.py`
  - the password gate on `POST /api/v1/2fa/devices/revoke-all`
- deleted detached `backend/app/services/two_factor_devices_api_service.py`
- deleted detached `backend/app/repositories/two_factor_devices_api_repository.py`

Effect:
- no mounted `/api/v1/2fa/*` route was removed
- the detached duplicate pair is gone
- the mixed route ownership around `/api/v1/2fa/devices*` is now explicitly
  documented and tested instead of being silently assumed
- protected auth cleanup moved forward without rewriting the broader 2FA flow
  or changing router include order
