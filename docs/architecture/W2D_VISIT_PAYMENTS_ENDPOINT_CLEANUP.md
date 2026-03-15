# Visit Payments Endpoint Cleanup

`backend/app/api/v1/endpoints/visit_payments.py` and
`backend/app/services/visit_payments_api_service.py` were detached legacy
entrypoint artifacts.

Verified facts:
- `backend/app/api/v1/api.py` did not include `visit_payments.router`
- `backend/openapi.json` exposed the mounted visit-payment read surface under
  `/api/v1/payments/visit/{visit_id}` from `payments.py`, not under
  `/api/v1/visit-payments/*`
- no live source imports of `backend/app/api/v1/endpoints/visit_payments.py`
  or `backend/app/services/visit_payments_api_service.py` were found in
  `backend/app` or `backend/tests`
- `backend/app/services/visit_payments_api_service.py` was an extra detached
  router-style shim living under `services/`, with no confirmed runtime owner
- the separately tested `backend/app/services/visit_payment_api_service.py`
  remains in place and was not changed by this cleanup

Cleanup performed:
- removed `backend/app/api/v1/endpoints/visit_payments.py`
- removed `backend/app/services/visit_payments_api_service.py`

Effect:
- no mounted runtime route was removed
- the live visit-payment read route remains owned by
  `backend/app/api/v1/endpoints/payments.py`
- dead visit-payments duplicate entrypoint residue is reduced without changing
  the active payment stack
