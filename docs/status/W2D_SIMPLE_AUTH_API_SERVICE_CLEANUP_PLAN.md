# Simple Auth API Service Cleanup Plan

Scope:
- review detached `backend/app/services/simple_auth_api_service.py`
- review detached `backend/app/repositories/simple_auth_api_repository.py`
- prove the mounted `/api/v1/auth/simple-login` owner with dedicated endpoint
  tests before any deletion
- prove the live `/api/v1/auth/me` response contract because frontend session
  consumers still depend on that path
- run the deterministic RBAC wrapper because this slice sits inside the auth
  routing surface
- allow only a narrow stale-test adjustment if verification still assumes the
  detached service file must exist

Evidence:
- the live routes are mounted from
  `backend/app/api/v1/endpoints/simple_auth.py`
- `backend/openapi.json` contains the published `/api/v1/auth/simple-login`
  and `/api/v1/auth/me` contracts
- live frontend usage remains on `/auth/me`
- the mounted owner already delegates login into `AuthFallbackService`
- no confirmed backend, test, docs, or frontend imports of the detached pair
  remain

Why this is safe:
- the mounted owner remains the only router file being changed indirectly by
  this cleanup
- dedicated endpoint proof lands before deleting the detached pair
- the auth verification pass includes `test_security_middleware.py` and
  `python test_role_routing.py`
- any verification fix is limited to the stale assumption that the detached
  service file must still exist

Out of scope:
- rewriting `/auth/me` ownership design
- rewriting token refresh, 2FA, or password-reset flows
- broad auth refactors
