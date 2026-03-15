# Next Execution Unit After Payment Settings API Service Cleanup

Recommended next step:
- a protected auth-adjacent plan-gate beginning with
  `backend/app/services/admin_users_api_service.py`

Required entry conditions:
- treat the first pass as audit/proof, not deletion-by-default
- confirm mounted owner, published routes, and live frontend/runtime usage
- keep `cashier_api_service.py` out of the first non-payment protected slice

Why:
- the payment duplicate lane is now exhausted
- remaining cleanup-capable candidates sit in auth, queue, or EMR-adjacent
  buckets
- `admin_users` is a narrower next protected entry point than reopening
  cashier
