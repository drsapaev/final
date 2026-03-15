# Password Reset API Service Cleanup Status

Status: completed

What changed:
- added dedicated password-reset endpoint contract tests
- fixed the mounted statistics RBAC dependency wiring in
  `backend/app/api/v1/endpoints/password_reset.py`
- deleted `backend/app/services/password_reset_api_service.py`
- deleted `backend/app/repositories/password_reset_api_repository.py`

Validation:
- targeted password-reset/OpenAPI/boundary verification passes
- `python test_role_routing.py` passes
- full backend suite passes

Result:
- `password_reset` is no longer an active protected residue candidate
- mounted `/api/v1/password-reset/*` behavior stays intact
- the next auth-adjacent protected follow-up now moves to
  `phone_verification`
