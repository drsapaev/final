# Payment Settings API Service Cleanup Plan

Scope:
- review detached `backend/app/services/payment_settings_api_service.py` and
  orphan `backend/app/repositories/payment_settings_api_repository.py`
- prove the mounted `/api/v1/admin/payment-provider-settings*` surface with
  dedicated endpoint tests before any deletion
- delete the detached pair only if the mounted owner already preserves the live
  contract

Evidence:
- live payment-settings routes are mounted from
  `backend/app/api/v1/endpoints/payment_settings.py`
- `backend/openapi.json` contains the published payment-settings endpoints
- `frontend/src/api/adminSettings.js` still uses the live mounted contract
- `backend/tests/unit/test_payment_settings_service.py` already protects the
  mounted domain service behavior

Why this is safe:
- the mounted owner remains the only public router owner
- endpoint proof lands before deleting the detached pair
- the slice does not alter cashier, payment-init, or webhook runtime

Out of scope:
- changing provider secret storage semantics
- rewriting payment settings validation logic
- refactoring cashier or payment-init architecture
