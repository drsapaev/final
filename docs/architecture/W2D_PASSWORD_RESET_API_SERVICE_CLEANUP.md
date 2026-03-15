# Password Reset API Service Cleanup

`backend/app/services/password_reset_api_service.py` and
`backend/app/repositories/password_reset_api_repository.py` were handled as a
protected auth-adjacent duplicate pair, not as a blind-delete candidate.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/password_reset.py` under
  `/api/v1/password-reset`
- `backend/openapi.json` publishes the live recovery surface:
  - `/api/v1/password-reset/initiate`
  - `/api/v1/password-reset/verify-phone`
  - `/api/v1/password-reset/confirm`
  - `/api/v1/password-reset/validate-token`
  - `/api/v1/password-reset/statistics`
- live frontend recovery usage remains in
  `frontend/src/components/auth/ForgotPassword.jsx`
- no live imports of the detached service or repository remained in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- the mounted owner already delegates to
  `backend/app/services/password_reset_service.py`
- the detached service file was effectively a router-style duplicate of the
  mounted owner, while the detached repository file had no live runtime role

Cleanup performed:
- added `backend/tests/integration/test_password_reset_endpoint_contract.py`
  to protect the live recovery contract and the admin-only statistics path
- fixed a narrow live auth drift in
  `backend/app/api/v1/endpoints/password_reset.py` by changing the statistics
  dependency from `require_roles(["Admin", "SuperAdmin"])` to
  `require_roles("Admin", "SuperAdmin")`
- deleted detached `backend/app/services/password_reset_api_service.py`
- deleted detached `backend/app/repositories/password_reset_api_repository.py`

Effect:
- no mounted `/api/v1/password-reset/*` route was removed
- the frontend-facing password-recovery contract now has dedicated endpoint
  proof
- admin-only statistics access now follows the intended RBAC path instead of
  failing inside the dependency factory
- protected auth cleanup moved forward without touching login, refresh, 2FA,
  or phone-verification runtime
