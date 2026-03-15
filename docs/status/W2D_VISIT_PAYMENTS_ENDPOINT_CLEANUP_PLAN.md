# Visit Payments Endpoint Cleanup Plan

Scope:
- delete dead endpoint artifact `backend/app/api/v1/endpoints/visit_payments.py`
- delete detached router shim `backend/app/services/visit_payments_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` does not mount `visit_payments.router`
- `backend/openapi.json` contains the mounted visit-payment read surface under
  `payments.py`, not under `/api/v1/visit-payments/*`
- no confirmed backend or test import of the endpoint module remains
- no confirmed backend or test import of `visit_payments_api_service.py`
  remains

Why this is safe:
- the endpoint file was not mounted, so deleting it cannot change runtime
  routing
- the extra `visit_payments_api_service.py` file had no confirmed live imports
- the live `visit_payment_api_service.py` module remains available and tested

Out of scope:
- rewriting manual payment integration helper scripts
- changing payment webhook behavior
- redesign of mounted payment APIs
