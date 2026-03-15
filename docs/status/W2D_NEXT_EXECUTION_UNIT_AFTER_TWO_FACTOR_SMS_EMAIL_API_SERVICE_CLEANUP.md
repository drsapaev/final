# Next Execution Unit After Two Factor SMS Email API Service Cleanup

Recommended next step:
- a protected auth-adjacent audit/proof pass for
  `backend/app/services/websocket_auth_api_service.py`

Required entry conditions:
- treat the first pass as audit/proof, not default deletion
- confirm mounted owner, live websocket/runtime usage, and auth impact before
  any mutation
- do not reopen `two_factor_devices` or `two_factor_sms_email`; both detached
  pairs are already gone
- do not widen the slice into queue or EMR runtime

Why:
- the remaining auth bucket is now down to websocket-auth
- the 2FA SMS/email duplicate pair is gone and the live frontend contract is
  aligned
- websocket-auth is the next protected candidate from the current residue
  inventory
