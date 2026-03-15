# W2D 2FA Devices Route Ownership Plan Gate

## Summary

After the protected duplicate-cleanup lane was exhausted, the next honest
follow-up was an audit-only ownership pass on the mixed
`/api/v1/2fa/devices*` surface.

This pass did not reorder routers or change the live 2FA runtime. It only
captured the current ownership split and its contract consequences.

## Findings

### Router order and first-match runtime

- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/two_factor_auth.py` before
  `backend/app/api/v1/endpoints/two_factor_devices.py`
- runtime first-match currently resolves:
  - `GET /api/v1/2fa/devices` to `two_factor_auth.get_trusted_devices`
  - `DELETE /api/v1/2fa/devices/{device_id}` to
    `two_factor_auth.untrust_device`
- the newer `two_factor_devices.py` owner still holds the rest of the
  device-management surface such as:
  - `POST /api/v1/2fa/devices`
  - `PUT /api/v1/2fa/devices/{device_id}/name`
  - `GET /api/v1/2fa/devices/{device_id}/sessions`
  - `POST /api/v1/2fa/devices/revoke-all`
  - `GET /api/v1/2fa/devices/statistics`

### Published contract versus runtime contract

- `backend/openapi.json` still publishes the `GET /api/v1/2fa/devices`
  operation from the `two-factor-devices` surface
- that published `GET` contract advertises an array response of `DeviceInfo`
- `backend/openapi.json` also publishes the `DELETE /api/v1/2fa/devices/{device_id}`
  operation from the `two-factor-devices` surface with the `Revoke Device`
  summary
- runtime behavior for the shadowed `GET` and `DELETE` operations remains the
  older auth-owner contract instead

### Frontend alignment

- `frontend/src/components/TwoFactorSettings.jsx` still expects a
  `response.devices` envelope from `GET /2fa/devices`
- `frontend/src/components/security/TwoFactorManager.jsx` still expects
  `response.data?.devices` and uses the current delete path behavior
- this means the frontend is aligned to the current runtime owner, not to the
  published `DeviceInfo[]` GET schema

### Proof now recorded

- `backend/tests/integration/test_two_factor_devices_endpoint_contract.py`
  already captures the live runtime payload shape for the shadowed `GET` and
  `DELETE` operations
- `backend/tests/integration/test_two_factor_devices_route_ownership_audit.py`
  now captures:
  - router-order first-match ownership
  - OpenAPI publication of the `two_factor_devices` owner shape

## Decision

This is not a cleanup candidate.

Do not:

- silently reorder the `/2fa` routers
- silently delete either runtime owner
- silently rewrite frontend payload expectations

Any future consolidation must be handled as a dedicated migration/parity plan
with explicit human review.

## Recommended next step

Open a dedicated human-reviewed `/api/v1/2fa/devices*` contract migration plan
that decides one of these outcomes explicitly:

- move published schema and frontend to the current auth-owner contract
- move runtime routing to the `two_factor_devices` owner contract
- split legacy and new device-management surfaces under different paths
