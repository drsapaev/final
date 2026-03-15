# W2D API Reference Queue Verification Plan

Scope:

- verify the `Queue` section in `docs/API_REFERENCE.md` against current OpenAPI
  and mounted queue owners
- keep the slice docs-only
- avoid rewriting the entire queue domain or changing protected queue runtime

Evidence targets:

- `backend/openapi.json`
- `backend/app/api/v1/endpoints/queue.py`
- `backend/app/api/v1/endpoints/qr_queue.py`
- `backend/app/api/v1/endpoints/queue_position.py`
- `backend/app/api/v1/endpoints/queue_reorder.py`

Expected outcome:

- stale pre-split queue route claims removed
- modern `/queue/*` versus `/queue/legacy/*` ownership made explicit
- unverified response claims downgraded where generated schema is not strong
