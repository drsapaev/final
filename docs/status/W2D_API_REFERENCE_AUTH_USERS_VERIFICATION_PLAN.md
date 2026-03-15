# W2D API Reference Authentication and Users Verification Plan

Scope:

- verify `docs/API_REFERENCE.md` against current OpenAPI and live mounted
  backend owners
- limit the pass to:
  - `Authentication`
  - `Users`
- keep the slice docs-only unless a live contract drift is required just to
  describe the current runtime honestly

Evidence targets:

- `backend/openapi.json`
- `backend/app/api/v1/endpoints/auth.py`
- `backend/app/api/v1/endpoints/authentication.py`
- `backend/app/api/v1/endpoints/user_management.py`

Expected outcome:

- stale auth request/response notes corrected
- stale `/users/me` claim removed
- current access notes for `/users/users*` made more accurate
