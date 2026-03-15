# W2D API Reference New Modules Links Verification Plan

Scope:

- verify the `New Modules` and `Links` footer sections in
  `docs/API_REFERENCE.md`
- keep the slice docs-only
- avoid turning the footer into a full route inventory or product-status rewrite

Evidence targets:

- `backend/openapi.json`
- `backend/app/main.py`
- `backend/app/api/v1/api.py`
- `backend/app/api/v1/endpoints/cardio.py`
- `backend/app/api/v1/endpoints/dental.py`
- `backend/app/api/v1/endpoints/messages.py`
- `backend/app/api/v1/endpoints/system_management.py`
- `backend/app/api/v1/endpoints/docs.py`
- websocket owners under `backend/app/ws/*`

Expected outcome:

- stale versioned `New Modules` claims downgraded to current curated route
  families
- canonical docs links separated from custom `/api/v1/docs/*` helpers
- placeholder websocket host removed in favor of mounted-family guidance
- next step shifted toward custom docs endpoint audit rather than more
  `API_REFERENCE.md` footer cleanup
