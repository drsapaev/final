# Admin Providers API Service Cleanup Plan

Scope:
- review detached `backend/app/services/admin_providers_api_service.py`
- prove the mounted `/api/v1/admin/providers*` owner with dedicated endpoint
  tests before any deletion
- if review finds narrow live drift, repair only that mounted contract and then
  remove the detached duplicate

Evidence:
- the live provider-management routes are mounted from
  `backend/app/api/v1/endpoints/admin_providers.py`
- `backend/openapi.json` contains the published `/api/v1/admin/providers*`
  contract
- no confirmed backend, test, docs, or frontend imports of the detached file
  remain
- live frontend usage still exists in `frontend/src/pages/Settings.jsx`, so
  endpoint proof is required before cleanup

Why this is safe:
- the mounted owner remains the only public router owner
- the contract fix is limited to the live provider update schema
- targeted endpoint proof lands before deleting the detached duplicate

Out of scope:
- changing `payment_settings` behavior
- changing cashier/payment-init/payment-webhook runtime
- changing provider secret storage design or production payment flows
