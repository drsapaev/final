# Payment Settings API Service Cleanup

`backend/app/services/payment_settings_api_service.py` was initially kept as a
protected divergent residue because it carried its own inline schemas and an
older repository path, even though the mounted payment-settings owner had
already moved to `PaymentSettingsService`.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/payment_settings.py`
- `backend/openapi.json` publishes the live payment-settings contract:
  - `/api/v1/admin/payment-provider-settings`
  - `/api/v1/admin/test-payment-provider`
  - `/api/v1/admin/payment-providers-info`
- no live imports of `payment_settings_api_service.py` or
  `payment_settings_api_repository.py` remained in `backend/app`,
  `backend/tests`, `docs`, or `frontend`
- live frontend usage remains in `frontend/src/api/adminSettings.js`
- live service coverage already existed in
  `backend/tests/unit/test_payment_settings_service.py`

Cleanup performed:
- added `backend/tests/integration/test_payment_settings_endpoint_contract.py`
  to protect the mounted GET/save/test/info endpoints
- removed detached `backend/app/services/payment_settings_api_service.py`
- removed orphan `backend/app/repositories/payment_settings_api_repository.py`
- narrowed `backend/tests/unit/test_service_repository_boundary.py` so it no
  longer requires the detached file to exist

Effect:
- no mounted payment-settings route was removed
- the live payment-settings owner stays on the `PaymentSettingsService` /
  `PaymentSettingsRepository` stack
- the protected payment duplicate lane is now effectively exhausted
- `cashier_api_service.py` remains a payment-critical non-cleanup artifact
