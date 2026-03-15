# Simple Auth API Service Cleanup Status

Status: completed

What changed:
- added dedicated simple-auth endpoint contract tests
- deleted `backend/app/services/simple_auth_api_service.py`
- deleted `backend/app/repositories/simple_auth_api_repository.py`
- updated the stale boundary test assumption so the detached service file may
  be absent

Validation:
- targeted simple-auth/auth-fallback/security/OpenAPI verification passes
- `python test_role_routing.py` passes
- full backend suite passes

Result:
- `simple_auth` is no longer an active protected residue candidate
- mounted `/api/v1/auth/simple-login` and `/api/v1/auth/me` behavior stay intact
- the next auth-adjacent protected follow-up now moves to `password_reset`
