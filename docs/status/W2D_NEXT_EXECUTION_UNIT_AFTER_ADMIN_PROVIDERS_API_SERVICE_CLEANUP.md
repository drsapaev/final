# Next Execution Unit After Admin Providers API Service Cleanup

Recommended next step:
- a protected review-first slice for
  `backend/app/services/payment_settings_api_service.py`

Required entry conditions:
- keep the live mounted
  `backend/app/api/v1/endpoints/payment_settings.py` owner unchanged unless a
  dedicated contract gap is proven
- use the existing payment settings service/unit coverage as the first proof
  layer
- keep `cashier_api_service.py` out of the first mutation pass

Why:
- `admin_providers` has been resolved with dedicated endpoint proof
- `payment_settings` is now the narrowest remaining payment-adjacent residue
  with behavior-bearing drift
- `cashier` remains a payment-critical architecture artifact, not a cleanup
  candidate
