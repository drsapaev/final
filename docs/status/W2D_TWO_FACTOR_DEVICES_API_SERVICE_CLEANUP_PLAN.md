# Two Factor Devices API Service Cleanup Plan

Scope:
- review detached `backend/app/services/two_factor_devices_api_service.py`
- review detached `backend/app/repositories/two_factor_devices_api_repository.py`
- prove the live `/api/v1/2fa/devices*` contract before any deletion
- account for mixed route ownership because `/api/v1/2fa` mounts both
  `two_factor_auth.py` and `two_factor_devices.py`
- avoid any router-order rewrite or broader 2FA redesign in this slice

Evidence:
- `backend/openapi.json` publishes the visible device-management paths
- live frontend usage remains in
  `frontend/src/components/TwoFactorSettings.jsx` and
  `frontend/src/components/security/TwoFactorManager.jsx`
- no confirmed backend, test, docs, or frontend imports of the detached pair
  remain
- diff vs the mounted owner is non-behavioral only
- runtime route introspection shows `GET/DELETE /api/v1/2fa/devices*` are
  shadowed by hidden `two_factor_auth.py` handlers, so the proof must cover
  both current runtime owner and unique `two_factor_devices.py` routes

Why this is safe:
- dedicated endpoint proof lands before deleting the detached pair
- no live route is removed or remapped
- the cleanup only touches the detached service/repository pair
- verification includes OpenAPI, boundary checks, and deterministic auth
  routing coverage

Out of scope:
- changing `/api/v1/2fa` router include order
- normalizing the mixed ownership between `two_factor_auth.py` and
  `two_factor_devices.py`
- rewriting SMS/email 2FA or websocket-auth runtime
