# W2D API Reference Payments Verification Status

Status: completed

What changed:

- the `Payments` section in `docs/API_REFERENCE.md` now reflects the current
  split between provider discovery, init flow, cashier creation, status/cancel,
  invoice routes, public webhooks, and reconciliation surfaces
- the stale `POST /payments/` request example was replaced with the live
  `visit_id` / `appointment_id` / `amount` / `currency` / `method` / `note`
  shape
- the section now explicitly includes `kaspi` webhook coverage and downgrades
  exact response claims where generated OpenAPI is still loose

Validation:

- `pytest tests/test_openapi_contract.py -q` -> `14 passed`
- route and schema claims were checked against:
  - `backend/openapi.json`
  - `backend/app/api/v1/endpoints/payments.py`
  - `backend/app/api/v1/endpoints/payment_webhooks.py`
  - `backend/app/api/v1/endpoints/payment_reconciliation.py`

Result:

- the touched payment docs no longer advertise the stale minimal payment flow
- the section now distinguishes public provider/webhook routes from
  authenticated cashier/admin payment operations more honestly
