# Next Execution Unit After Admin Users API Service Cleanup

Recommended next step:
- a protected auth-adjacent audit/proof pass for
  `backend/app/services/minimal_auth_api_service.py`

Required entry conditions:
- treat the first pass as audit/proof, not default deletion
- confirm mounted owner, published routes, live runtime usage, and RBAC impact
  before any mutation
- do not rewrite login, token, or 2FA flows during the first pass

Why:
- `admin_users` now has dedicated endpoint/RBAC proof and the detached pair is
  gone
- the remaining auth bucket is still protected and must be handled one file at
  a time
- `minimal_auth_api_service.py` is the next auth-adjacent candidate from the
  current strategic residue inventory
