# Minimal Auth API Service Cleanup

`backend/app/services/minimal_auth_api_service.py` and
`backend/app/repositories/minimal_auth_api_repository.py` were treated as a
protected auth-adjacent duplicate pair rather than a blind-delete candidate.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/minimal_auth.py` under `/api/v1/auth`
- `backend/openapi.json` publishes the live `/api/v1/auth/minimal-login`
  contract
- live frontend usage remains in
  `frontend/src/components/auth/LoginFormStyled.jsx`
- no live imports of the detached service or repository remained in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- the mounted owner already delegates through
  `backend/app/services/auth_fallback_service.py` and
  `backend/app/repositories/auth_fallback_repository.py`
- `AuthFallbackRepository.get_user_credentials_row()` preserves the same
  direct-SQL lookup shape that the detached file previously inlined

Cleanup performed:
- added `backend/tests/integration/test_minimal_auth_endpoint_contract.py`
  to protect email-based login, `remember_me` expiry, and invalid-password
  behavior for the mounted owner
- deleted detached `backend/app/services/minimal_auth_api_service.py`
- deleted detached `backend/app/repositories/minimal_auth_api_repository.py`
- narrowly updated
  `backend/tests/unit/test_service_repository_boundary.py` so the boundary test
  no longer requires the detached service file to exist

Effect:
- no mounted `/api/v1/auth/minimal-login` route was removed
- the live minimal-auth surface now has dedicated endpoint proof
- auth-adjacent cleanup moved forward without touching login, token refresh,
  2FA, or password-reset runtime
