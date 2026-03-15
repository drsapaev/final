# Admin Users API Service Cleanup

`backend/app/services/admin_users_api_service.py` and
`backend/app/repositories/admin_users_api_repository.py` were treated as a
protected auth-adjacent duplicate pair rather than a blind-delete candidate.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/admin_users.py`
- `backend/openapi.json` publishes the live `/api/v1/admin/users` contract
- live frontend usage remains in `frontend/src/pages/UserSelect.jsx`
- no live imports of the detached service or repository remained in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- the mounted owner already delegates through
  `backend/app/services/admin_users_service.py` and
  `backend/app/repositories/admin_users_repository.py`
- dedicated endpoint/RBAC proof for `/api/v1/admin/users` did not exist before
  this slice

Cleanup performed:
- added `backend/tests/integration/test_admin_users_endpoint_contract.py`
  to protect the mounted payload shape and non-admin `403` denial
- deleted detached `backend/app/services/admin_users_api_service.py`
- deleted detached `backend/app/repositories/admin_users_api_repository.py`
- narrowly updated
  `backend/tests/unit/test_service_repository_boundary.py` so the boundary test
  no longer requires the detached file to exist

Effect:
- no mounted `/api/v1/admin/users` route was removed
- the live admin-users surface now has dedicated endpoint/RBAC proof
- auth-adjacent cleanup moved forward without touching login, token, 2FA, or
  password-reset runtime
