# User Data Transfer API Service Cleanup

`backend/app/services/user_data_transfer_api_service.py` was a detached
router-style residue for the mounted user data transfer endpoint owner.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/user_data_transfer.py` with
  `prefix="/admin/user-data"`
- `backend/openapi.json` exposes the live `/api/v1/admin/user-data/*` routes
  owned by the mounted endpoint file, including user data summary, search,
  transfer, confirmation, history, statistics, validation, and data-types
  routes
- no live source imports of
  `backend/app/services/user_data_transfer_api_service.py` were found in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- `backend/app/services/user_data_transfer_api_service.py` differed from the
  mounted owner only by stale imports and typing drift and no longer owned
  runtime route behavior

Cleanup performed:
- removed `backend/app/services/user_data_transfer_api_service.py`

Effect:
- no mounted runtime route was removed
- live user data transfer route ownership remains unchanged
- one more dead router-style service residue is gone
