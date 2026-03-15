# Phone Verification API Service Cleanup Plan

Scope:
- review detached `backend/app/services/phone_verification_api_service.py`
- review detached `backend/app/repositories/phone_verification_api_repository.py`
- prove the mounted `/api/v1/phone-verification/*` owner with dedicated
  endpoint tests before any deletion
- prove both user-facing and admin-facing contracts because frontend usage
  remains live in auth and admin UI surfaces
- allow only a narrow live drift fix if verification exposes a mounted-owner
  RBAC wiring mistake

Evidence:
- the live routes are mounted from
  `backend/app/api/v1/endpoints/phone_verification.py`
- `backend/openapi.json` contains the published phone-verification routes
- live frontend usage remains in
  `frontend/src/components/auth/PhoneVerification.jsx` and
  `frontend/src/components/admin/PhoneVerificationManager.jsx`
- no confirmed backend, test, docs, or frontend imports of the detached pair
  remain
- diff vs the mounted owner is non-behavioral typing drift only

Why this is safe:
- dedicated endpoint proof lands before deleting the detached pair
- the mounted owner remains the only runtime file touched
- the only allowed runtime edit is a narrow auth dependency correction if
  verification proves that current mounted behavior is broken
- verification includes OpenAPI, boundary checks, and deterministic RBAC
  coverage

Out of scope:
- rewriting password-reset, login, refresh, websocket-auth, or 2FA flows
- redesigning SMS provider behavior
- broad auth refactors
