# W2D Payment Protected Residue Plan Gate

## Summary

After the non-protected cleanup lane was exhausted, the next honest follow-up
was a payment-adjacent protected audit on:

- `backend/app/services/admin_providers_api_service.py`
- `backend/app/services/payment_settings_api_service.py`
- `backend/app/services/cashier_api_service.py`

This pass was audit-only. No payment runtime files were deleted or rewritten.

## Findings

### `admin_providers_api_service.py`

- mounted owner remains in
  `backend/app/api/v1/endpoints/admin_providers.py`
- `backend/app/api/v1/api.py` mounts that owner
- `backend/openapi.json` still publishes `/api/v1/admin/providers*`
- no live imports of `admin_providers_api_service.py` were found in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- diff vs mounted owner is effectively cosmetic typing drift only
- live frontend usage still exists in
  `frontend/src/pages/Settings.jsx` for:
  - `GET /admin/providers`
  - `POST /admin/providers`
  - `PUT /admin/providers/{provider_id}`
  - `DELETE /admin/providers/{provider_id}`
- a protected follow-up added
  `backend/tests/integration/test_admin_providers_endpoint_contract.py`
- follow-up review found and repaired a narrow live-contract issue:
  `PaymentProviderUpdate` needed optional `name` and `code` to safely accept
  the payload shape already sent by the frontend
- the detached duplicate has since been removed

Verdict:

- resolved via protected proof plus narrow contract restoration

### `payment_settings_api_service.py`

- mounted owner remains in
  `backend/app/api/v1/endpoints/payment_settings.py`
- live mounted owner already delegates to
  `backend/app/services/payment_settings_service.py`
- live repository owner is
  `backend/app/repositories/payment_settings_repository.py`
- `backend/openapi.json` publishes:
  - `/api/v1/admin/payment-provider-settings`
  - `/api/v1/admin/test-payment-provider`
  - `/api/v1/admin/payment-providers-info`
- frontend usage remains live in
  `frontend/src/api/adminSettings.js`
- no live imports of `payment_settings_api_service.py` were found
- diff vs mounted owner is behavior-bearing, not cosmetic:
  - detached file carries its own inline schemas
  - detached file uses the older `PaymentSettingsApiRepository`
  - mounted owner uses `PaymentSettingsService` and
    `PaymentSettingsRepository`
- live service coverage exists in
  `backend/tests/unit/test_payment_settings_service.py`
- a protected follow-up added
  `backend/tests/integration/test_payment_settings_endpoint_contract.py`
- that follow-up confirmed the mounted owner already preserves the live
  frontend-facing contract, allowing the detached service and repository pair
  to be removed

Verdict:

- resolved after dedicated endpoint proof

### `cashier_api_service.py`

- cashier routes remain mounted from
  `backend/app/api/v1/endpoints/cashier.py`
- `backend/openapi.json` publishes the live `/api/v1/cashier/*` surface
- frontend usage is broad and live through
  `frontend/src/hooks/usePayments.js`
- the mounted endpoint is still payment-critical and direct-ORM-heavy
- `backend/tests/unit/test_service_repository_boundary.py` still reads the
  service logic block from `cashier_api_service.py`
- existing W2A docs already classify cashier as payment-coupled and pending
  human review

Verdict:

- not a cleanup candidate
- treat as payment-critical architecture artifact / future refactor surface,
  not detached residue to delete

## Decision

Current payment cluster split:

- `admin_providers_api_service.py`: resolved
- `payment_settings_api_service.py`: resolved
- `cashier_api_service.py`: not-cleanup candidate

This plan-gate began as an audit-only pass. A later protected follow-up
resolved `admin_providers` and `payment_settings` after dedicated endpoint
proof. The remaining payment cluster no longer contains cleanup-capable
duplicates.

## Recommended next step

Shift the next human-reviewed protected follow-up away from payments and into
the auth/queue/EMR buckets, while keeping `cashier_api_service.py` out of
cleanup.
