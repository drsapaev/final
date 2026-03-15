# W2D Custom Docs Endpoints Verification Plan

Scope:

- audit the mounted helper endpoints in `backend/app/api/v1/endpoints/docs.py`
- keep the slice bounded to content and helper-response correctness
- avoid changing generated docs routing or protected runtime behavior

Evidence targets:

- `backend/app/api/v1/endpoints/docs.py`
- `backend/app/api/v1/api.py`
- `backend/app/main.py`
- `backend/openapi.json`

Expected outcome:

- `api-docs` becomes a lightweight landing page instead of a stale brochure
- `api-schema` stops returning a fake hand-maintained mini-schema
- `endpoints-summary` stops returning hardcoded counts and route samples
- targeted tests protect the live helper behavior
