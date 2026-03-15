# Admin Providers API Service Cleanup Status

Status: completed

What changed:
- added dedicated admin provider endpoint contract tests
- widened the live `PaymentProviderUpdate` schema with `name` and `code`
- deleted `backend/app/services/admin_providers_api_service.py`

Validation:
- targeted admin-provider plus OpenAPI contract tests pass
- full backend suite passes

Result:
- `admin_providers` is no longer an active protected residue candidate
- mounted `/api/v1/admin/providers*` ownership stays intact
- the payment protected follow-up now narrows to `payment_settings` review and
  `cashier` staying out of cleanup
