# W2D API Reference Analytics Verification Plan

Scope:

- verify the `Analytics` section in `docs/API_REFERENCE.md` against current
  OpenAPI and mounted analytics owners
- keep the slice docs-only
- avoid turning the pass into a full analytics specification rewrite

Evidence targets:

- `backend/openapi.json`
- `backend/app/api/v1/endpoints/analytics.py`
- `backend/app/api/v1/endpoints/advanced_analytics.py`
- `backend/app/api/v1/endpoints/ai_analytics.py`
- `backend/app/api/v1/endpoints/wait_time_analytics.py`

Expected outcome:

- removed top-level analytics route claims deleted
- current analytics route families and public health exceptions reflected
- broad or under-typed response claims downgraded instead of guessed
