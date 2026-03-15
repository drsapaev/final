# Next Execution Unit After Password Reset API Service Cleanup

Recommended next step:
- a protected auth-adjacent audit/proof pass for
  `backend/app/services/phone_verification_api_service.py`

Required entry conditions:
- treat the first pass as audit/proof, not default deletion
- confirm mounted owner, published routes, live runtime usage, and auth impact
  before any mutation
- do not reopen `admin_users`, `minimal_auth`, `simple_auth`, or
  `password_reset`; all four have already been resolved with dedicated proof
- do not widen the slice into 2FA or websocket-auth runtime

Why:
- `password_reset` now has dedicated endpoint proof and the detached pair is
  gone
- the remaining auth bucket is still protected and must be handled one file at
  a time
- `phone_verification_api_service.py` is the next auth-adjacent candidate from
  the current strategic residue inventory
