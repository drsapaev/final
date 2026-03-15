# Next Execution Unit After Custom Docs Endpoints Verification

Recommended next step:

- completed via
  `docs/architecture/W2D_API_DOCUMENTATION_ROUTER_VERIFICATION.md`

Why:

- the `docs.py` helper endpoints are now aligned to the generated contract
- the neighboring `/api/v1/documentation/*` router was the clearest remaining
  low-risk docs-vs-code drift target and has now been corrected

Current next step now lives in:

- `docs/status/W2D_NEXT_EXECUTION_UNIT_AFTER_API_DOCUMENTATION_ROUTER_VERIFICATION.md`

Required entry conditions:

- keep the next slice bounded and docs-first
- prefer narrowing or downgrading stale claims over inventing a new custom spec
- treat `/docs` and `/openapi.json` as canonical when the custom runtime docs
  disagree
