# Payment Settings API Service Cleanup Status

Status: completed

What changed:
- added payment-settings endpoint contract tests
- deleted `backend/app/services/payment_settings_api_service.py`
- deleted `backend/app/repositories/payment_settings_api_repository.py`
- narrowed the stale boundary test that still required the detached file

Validation:
- payment-settings targeted endpoint, service, boundary, and OpenAPI tests pass
- full backend suite passes

Result:
- `payment_settings` is no longer an active protected residue candidate
- the payment duplicate-cleanup lane is effectively finished
- `cashier` remains explicitly outside cleanup
