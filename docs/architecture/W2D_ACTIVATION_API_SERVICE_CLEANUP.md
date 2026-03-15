# Activation API Service Cleanup

`backend/app/services/activation_api_service.py` and
`backend/app/repositories/activation_api_repository.py` were detached residue
after the mounted activation owner moved to
`backend/app/api/v1/endpoints/activation.py` plus
`backend/app/services/activation_admin_service.py`.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/activation.py`
- `backend/openapi.json` publishes the live `/api/v1/activation/*` routes:
  `issue`, `activate`, `status`, `list`, `revoke`, and `extend`
- no live imports of `activation_api_service.py` or
  `activation_api_repository.py` remained in `backend/app`, `backend/tests`,
  `docs`, or `frontend`
- the remaining inline list/revoke/extend logic in the detached file matched
  the active `ActivationAdminService` + `ActivationAdminRepository` contract
  closely enough to treat the difference as implementation shape rather than
  runtime behavior

Cleanup performed:
- removed `backend/app/services/activation_api_service.py`
- removed `backend/app/repositories/activation_api_repository.py`
- redirected the service-boundary test to the live
  `activation_admin_service.py` owner
- added integration coverage for activation admin `list`, `revoke`, and
  `extend` endpoints

Effect:
- no mounted activation route was removed
- live activation admin behavior stays owned by the mounted endpoint and admin
  service stack
- one more detached service/repository residue pair is gone
