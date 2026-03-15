# Minimal Auth API Service Cleanup Plan

Scope:
- review detached `backend/app/services/minimal_auth_api_service.py`
- review detached `backend/app/repositories/minimal_auth_api_repository.py`
- prove the mounted `/api/v1/auth/minimal-login` owner with dedicated endpoint
  tests before any deletion
- run the deterministic RBAC wrapper because this path is part of the auth
  routing surface
- allow only a narrow stale-test adjustment if verification still assumes the
  detached service file must exist

Evidence:
- the live route is mounted from
  `backend/app/api/v1/endpoints/minimal_auth.py`
- `backend/openapi.json` contains the published `/api/v1/auth/minimal-login`
  contract
- live frontend usage remains in
  `frontend/src/components/auth/LoginFormStyled.jsx`
- the mounted owner already delegates into `AuthFallbackService`
- `AuthFallbackRepository` preserves the direct SQL credentials lookup used by
  the live path
- no confirmed backend, test, docs, or frontend imports of the detached pair
  remain

Why this is safe:
- the mounted owner remains the only public router owner
- dedicated endpoint proof lands before deleting the detached pair
- the auth verification pass includes `test_security_middleware.py` and
  `python test_role_routing.py`
- any verification fix is limited to the stale assumption that the detached
  service file must still exist

Out of scope:
- rewriting login, refresh-token, 2FA, or password-reset flows
- changing the `AuthFallbackService` runtime contract
- broad auth refactors
