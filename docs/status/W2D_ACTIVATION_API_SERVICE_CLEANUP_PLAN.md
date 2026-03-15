# Activation API Service Cleanup Plan

Scope:
- remove detached activation router residue
  `backend/app/services/activation_api_service.py`
- remove orphan generic repository residue
  `backend/app/repositories/activation_api_repository.py`

Evidence:
- the live activation routes are mounted from
  `backend/app/api/v1/endpoints/activation.py`
- `backend/openapi.json` contains the live `/api/v1/activation/*` contract
- no confirmed backend, test, docs, or frontend imports of the detached pair
  remain
- the live admin `list/revoke/extend` behavior is already covered by
  `ActivationAdminService` and `ActivationAdminRepository`

Why this is safe:
- the detached files are not mounted owners
- the live activation runtime remains in the endpoint owner plus admin service
  stack
- targeted endpoint tests protect the admin contract before cleanup

Out of scope:
- changing activation issuance or activation-token behavior
- changing auth, licensing, or protected security middleware behavior
