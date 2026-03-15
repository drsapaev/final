# Admin Users API Service Cleanup Status

Status: completed

What changed:
- added dedicated admin-users endpoint/RBAC contract tests
- deleted `backend/app/services/admin_users_api_service.py`
- deleted `backend/app/repositories/admin_users_api_repository.py`
- updated the stale boundary test assumption so the detached service file may
  be absent

Validation:
- targeted admin-users/RBAC/OpenAPI verification passes
- full backend suite passes

Result:
- `admin_users` is no longer an active protected residue candidate
- mounted `/api/v1/admin/users` ownership and RBAC behavior stay intact
- the next auth-adjacent protected follow-up now moves deeper into the
  remaining auth inventory instead of reopening `admin_users`
