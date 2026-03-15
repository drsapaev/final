# W2D API Reference Settings and Notifications Verification Plan

Scope:

- verify `docs/API_REFERENCE.md` against current OpenAPI and live mounted
  backend owners
- limit the pass to:
  - document framing
  - `Notifications`
  - `Settings`
- avoid turning the slice into a full manual rewrite of the entire API
  document

Evidence targets:

- `backend/openapi.json`
- `backend/app/api/v1/endpoints/notifications.py`
- `backend/app/api/v1/endpoints/settings.py`

Expected outcome:

- stale route/path claims removed
- stale payload examples corrected
- `API_REFERENCE.md` explicitly framed as a curated reference, not an exact
  full inventory
