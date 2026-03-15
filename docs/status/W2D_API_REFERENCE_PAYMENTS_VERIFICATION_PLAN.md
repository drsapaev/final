# W2D API Reference Payments Verification Plan

Scope:

- verify the `Payments` section in `docs/API_REFERENCE.md` against current
  OpenAPI and mounted payment owners
- keep the slice docs-only inside the protected payments domain
- avoid changing payment runtime behavior

Evidence targets:

- `backend/openapi.json`
- `backend/app/api/v1/endpoints/payments.py`
- `backend/app/api/v1/endpoints/payment_webhooks.py`
- `backend/app/api/v1/endpoints/payment_reconciliation.py`

Expected outcome:

- stale payment flow claims removed
- live payment init/status/invoice/webhook surfaces reflected more honestly
- under-typed response claims downgraded instead of guessed
