# Password Reset API Service Cleanup Plan

Scope:
- review detached `backend/app/services/password_reset_api_service.py`
- review detached `backend/app/repositories/password_reset_api_repository.py`
- prove the mounted `/api/v1/password-reset/*` owner with dedicated endpoint
  tests before any deletion
- prove the admin-only `/api/v1/password-reset/statistics` contract because it
  sits inside a protected auth-adjacent surface
- allow only a narrow live drift fix if verification exposes a mounted-owner
  RBAC wiring mistake

Evidence:
- the live routes are mounted from
  `backend/app/api/v1/endpoints/password_reset.py`
- `backend/openapi.json` contains the published password-reset routes
- live frontend usage remains in
  `frontend/src/components/auth/ForgotPassword.jsx`
- the mounted owner already delegates into `PasswordResetService`
- no confirmed backend, test, docs, or frontend imports of the detached pair
  remain

Why this is safe:
- dedicated endpoint proof lands before deleting the detached pair
- the mounted owner remains the only runtime file touched
- the only allowed runtime edit is a narrow auth dependency correction if
  verification proves that current mounted behavior is broken
- verification includes OpenAPI, boundary checks, and deterministic RBAC
  coverage

Out of scope:
- rewriting login, refresh, or 2FA flows
- redesigning password-reset token lifecycle
- broad auth refactors
