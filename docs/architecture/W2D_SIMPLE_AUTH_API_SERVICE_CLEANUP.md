# Simple Auth API Service Cleanup

`backend/app/services/simple_auth_api_service.py` and
`backend/app/repositories/simple_auth_api_repository.py` were treated as a
protected auth-adjacent duplicate pair rather than a blind-delete candidate.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/simple_auth.py` under `/api/v1/auth`
- `backend/openapi.json` publishes the live `/api/v1/auth/simple-login` and
  `/api/v1/auth/me` contracts
- live frontend/session usage remains on `/auth/me` in
  `frontend/src/api/client.js`,
  `frontend/src/services/auth.js`, and
  `frontend/src/components/auth/LoginFormStyled.jsx`
- no live imports of the detached service or repository remained in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- the mounted owner already delegates the login path through
  `backend/app/services/auth_fallback_service.py` and
  `backend/app/repositories/auth_fallback_repository.py`
- dedicated endpoint proof confirmed that the live `/api/v1/auth/me` surface
  still returns the authenticated profile contract after cleanup

Cleanup performed:
- added `backend/tests/integration/test_simple_auth_endpoint_contract.py`
  to protect the live `/api/v1/auth/simple-login` contract and the current
  authenticated `/api/v1/auth/me` response shape
- deleted detached `backend/app/services/simple_auth_api_service.py`
- deleted detached `backend/app/repositories/simple_auth_api_repository.py`
- narrowly updated
  `backend/tests/unit/test_service_repository_boundary.py` so the boundary test
  no longer requires the detached service file to exist

Effect:
- no mounted `/api/v1/auth/simple-login` or `/api/v1/auth/me` route was removed
- the live simple-auth surface now has dedicated endpoint proof
- auth-adjacent cleanup moved forward without touching token refresh, 2FA, or
  password-reset runtime
