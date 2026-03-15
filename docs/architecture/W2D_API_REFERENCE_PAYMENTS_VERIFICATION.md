# W2D API Reference Payments Verification

## Summary

This was a bounded docs-vs-code verification pass for `docs/API_REFERENCE.md`.

The goal was not to fully re-document the whole payment subsystem. The goal was
to correct high-confidence drift in the `Payments` section while keeping the
slice docs-only inside a protected payment domain.

## Findings

### Payments section was still documenting an older minimal payment flow

- the doc still advertised only:
  - `GET /payments/`
  - `POST /payments/`
  - `POST /payments/webhook/payme`
  - `POST /payments/webhook/click`
- the live payment contract is broader and now includes:
  - `GET /api/v1/payments/providers`
  - `POST /api/v1/payments/init`
  - `GET /api/v1/payments/{payment_id}`
  - `POST /api/v1/payments/{payment_id}/cancel`
  - `POST /api/v1/payments/invoice/create`
  - `GET /api/v1/payments/invoices/pending`
  - `POST /api/v1/payments/webhook/kaspi`
  - `/api/v1/payments/reconcile/*`

### Create-payment request shape had drifted

- the doc still used `provider` and `discount_percent` on `POST /payments/`
- the live `PaymentCreateRequest` now uses:
  - `visit_id`
  - `appointment_id`
  - `amount`
  - `currency`
  - `method`
  - `note`
- provider-backed payment initialization moved to
  `POST /api/v1/payments/init`

### Access notes are now more differentiated than the old section implied

- `GET /api/v1/payments/providers` is public
- `POST /api/v1/payments/init` requires `Admin`, `Registrar`, or `Cashier`
- `POST /api/v1/payments/` requires `Admin` or `Cashier`
- `GET /api/v1/payments/` requires `Admin`, `Cashier`, `Registrar`, or
  `Doctor`
- `GET /api/v1/payments/{payment_id}` also allows `Patient`
- provider webhooks under `/payments/webhook/*` are public callback routes

### Not every live response shape is strongly typed in generated schema

- `POST /api/v1/payments/`, `POST /api/v1/payments/{payment_id}/cancel`,
  webhook routes, and reconciliation routes currently expose free-form object
  responses in generated `backend/openapi.json`
- the honest docs move was to document the stable request/access story and
  downgrade exact response-shape claims where the contract is still loose

## What changed

- updated the `Payments` section in `docs/API_REFERENCE.md` to a curated modern
  payments map
- separated provider discovery, init flow, cashier creation, status/cancel, and
  invoice routes
- corrected the `POST /payments/` request shape
- expanded public webhook coverage to include `kaspi`
- marked additional payment reconciliation and diagnostic routes as active but
  not fully re-documented in this bounded slice

## Evidence used

- `backend/openapi.json`
- `backend/app/api/v1/endpoints/payments.py`
- `backend/app/api/v1/endpoints/payment_webhooks.py`
- `backend/app/api/v1/endpoints/payment_reconciliation.py`

## Recommended next step

Continue the broader `API_REFERENCE.md` verification track with another bounded
slice rather than a full rewrite.

Best next candidate:

- `Analytics`
