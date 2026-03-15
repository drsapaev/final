# Admin Providers API Service Cleanup

`backend/app/services/admin_providers_api_service.py` started as a protected
payment-adjacent duplicate candidate rather than a safe blind delete.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/admin_providers.py`
- `backend/openapi.json` publishes the live `/api/v1/admin/providers*`
  contract
- no live imports of `admin_providers_api_service.py` remained in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- live frontend usage still exists in `frontend/src/pages/Settings.jsx` for
  `GET`, `POST`, `PUT`, and `DELETE /admin/providers*`
- dedicated endpoint-contract coverage for that surface did not exist before
  this slice
- review found a real live-contract bug: `PaymentProviderUpdate` did not expose
  `name` or `code`, so the mounted `PUT /api/v1/admin/providers/{provider_id}`
  path could not safely handle the payload shape already sent by the frontend

Cleanup performed:
- added `backend/tests/integration/test_admin_providers_endpoint_contract.py`
  to protect list/create/get/update/delete behavior for the live mounted owner
- widened `PaymentProviderUpdate` with optional `name` and `code` so the
  mounted owner preserves the expected update path
- deleted detached `backend/app/services/admin_providers_api_service.py`

Effect:
- no mounted `/api/v1/admin/providers*` route was removed
- the live provider-management surface now has dedicated backend proof
- payment-adjacent cleanup moved forward without touching
  `payment_settings_api_service.py` or `cashier_api_service.py`
- the payment protected residue cluster is now thinner and more explicit
