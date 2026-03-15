# Admin Users API Service Cleanup Plan

Scope:
- review detached `backend/app/services/admin_users_api_service.py`
- review detached `backend/app/repositories/admin_users_api_repository.py`
- prove the mounted `/api/v1/admin/users` owner with dedicated endpoint/RBAC
  tests before any deletion
- allow only a narrow stale-test adjustment if verification still assumes the
  detached files must exist

Evidence:
- the live route is mounted from
  `backend/app/api/v1/endpoints/admin_users.py`
- `backend/openapi.json` contains the published `/api/v1/admin/users`
  contract
- live frontend usage remains in `frontend/src/pages/UserSelect.jsx`
- no confirmed backend, test, docs, or frontend imports of the detached
  service/repository pair remain
- existing unit coverage already protects `AdminUsersService` and
  `AdminUsersRepository`

Why this is safe:
- the mounted owner remains the only public router owner
- dedicated endpoint proof lands before deleting the detached pair
- any verification fix is limited to the stale assumption that the detached
  files must still exist

Out of scope:
- rewriting login, token, 2FA, or password-reset flows
- changing admin role semantics outside the already-mounted `/admin/users`
  contract
- broad auth refactors
