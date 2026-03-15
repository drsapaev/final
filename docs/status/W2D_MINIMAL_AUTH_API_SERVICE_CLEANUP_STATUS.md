# Minimal Auth API Service Cleanup Status

Status: completed

What changed:
- added dedicated minimal-auth endpoint contract tests
- deleted `backend/app/services/minimal_auth_api_service.py`
- deleted `backend/app/repositories/minimal_auth_api_repository.py`
- updated the stale boundary test assumption so the detached service file may
  be absent

Validation:
- targeted minimal-auth/auth-fallback/security/OpenAPI verification passes
- `python test_role_routing.py` passes
- full backend suite passes

Result:
- `minimal_auth` is no longer an active protected residue candidate
- mounted `/api/v1/auth/minimal-login` ownership and auth behavior stay intact
- the next auth-adjacent protected follow-up now moves to `simple_auth`
