# Next Execution Unit After API Reference New Modules Links Verification

Recommended next step:

- completed via `docs/architecture/W2D_CUSTOM_DOCS_ENDPOINTS_VERIFICATION.md`

Why:

- the remaining `API_REFERENCE.md` footer/reference drift is now largely
  exhausted
- `New Modules` and `Links` were the last clear low-risk footer candidates
- the next obvious stale-doc surface is no longer Markdown-only; it is the
  mounted `/api/v1/docs/*` runtime content
- `backend/app/api/v1/endpoints/docs.py` was the next clear target and has now
  been corrected in a bounded helper-docs pass

Current next step now lives in:

- `docs/status/W2D_NEXT_EXECUTION_UNIT_AFTER_CUSTOM_DOCS_ENDPOINTS_VERIFICATION.md`

Required entry conditions:

- treat the next step as a docs-vs-code audit, not as a runtime product rewrite
- prefer narrow content correction inside `docs.py` over structural API changes
- keep generated `/docs` and `/openapi.json` as canonical when custom embedded
  docs disagree
