# W2D API Reference Health Auth Header Verification Plan

Scope:

- verify the `Health` and `Authentication Header` sections in
  `docs/API_REFERENCE.md` against current OpenAPI and mounted owners
- keep the slice docs-only
- avoid turning the pass into a full auth or observability specification rewrite

Evidence targets:

- `backend/openapi.json`
- `backend/app/api/v1/api.py`
- `backend/app/api/v1/endpoints/health.py`

Expected outcome:

- stale root `/` health claim removed from the API-scoped reference
- live `/health` and `/status` owner shape reflected
- adjacent public versus authenticated health-style routes called out
- authentication header guidance aligned to the current published
  `OAuth2PasswordBearer` scheme
- generic “all routes are protected” implication downgraded
