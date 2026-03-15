# Next Execution Unit After Minimal Auth API Service Cleanup

Recommended next step:
- a protected auth-adjacent audit/proof pass for
  `backend/app/services/simple_auth_api_service.py`

Required entry conditions:
- treat the first pass as audit/proof, not default deletion
- confirm mounted owner, published routes, live runtime usage, and auth impact
  before any mutation
- do not rewrite login, refresh-token, or 2FA flows during the first pass

Why:
- `minimal_auth` now has dedicated endpoint proof and the detached pair is
  gone
- the remaining auth bucket is still protected and must be handled one file at
  a time
- `simple_auth_api_service.py` is the next auth-adjacent candidate from the
  current strategic residue inventory
