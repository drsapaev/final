# W2D Custom Docs Endpoints Verification

## Summary

This was a bounded docs-vs-code audit for the mounted custom docs helper
endpoints in `backend/app/api/v1/endpoints/docs.py`.

The goal was not to redesign generated docs. The goal was to stop the helper
endpoints from serving a stale mini-spec that drifted away from the live API.

## Findings

### `GET /api/v1/docs/api-docs` had become a stale HTML brochure

- it still advertised old paths and assumptions such as:
  - `/api/v1/users/me`
  - `/api/v1/users/`
  - `/api/v1/visits/`
  - `/api/v1/analytics/payment-providers`
  - `Nurse` in the compact role list
  - `/api/v1/health` as the helpful link target
- several of those examples no longer reflect the current mounted or published
  contract
- the honest fix was to turn the page into a lightweight landing page that
  points back to canonical generated docs and only highlights selected live
  route families

### `GET /api/v1/docs/api-schema` returned a fake hand-maintained schema

- the old response claimed:
  - `openapi: 3.0.0`
  - `version: 1.0.0`
  - a tiny hardcoded `paths` object
  - a custom `BearerAuth` security scheme
- the live generated schema is much broader and now uses the app’s actual
  `OAuth2PasswordBearer` setup
- the safest fix was to return the current `request.app.openapi()` result
  directly instead of maintaining a second schema by hand

### `GET /api/v1/docs/endpoints-summary` was a hardcoded snapshot

- it still claimed:
  - `total_endpoints: 45`
  - tiny static categories
  - old route samples such as `/users/{id}/activate`, `/patients/search`, and
    `/analytics/payment-providers`
- current generated OpenAPI publishes hundreds of paths, not a 45-endpoint app
- the honest fix was to replace the hardcoded snapshot with a live generated
  summary based on the current OpenAPI schema

## What changed

- replaced the stale `api-docs` HTML brochure with a lightweight landing page
  that points readers to `/docs`, `/redoc`, `/openapi.json`,
  `/api/v1/docs/api-schema`, and `/api/v1/docs/endpoints-summary`
- changed `api-schema` to return the live generated OpenAPI document
- changed `endpoints-summary` to build path counts, operation counts, top tags,
  sample route families, and websocket-family notes from the current schema
- added integration coverage for the three custom docs endpoints

## Evidence used

- `backend/app/api/v1/endpoints/docs.py`
- `backend/app/api/v1/endpoints/api_documentation.py`
- `backend/app/api/v1/api.py`
- `backend/app/main.py`
- `backend/openapi.json`

## Verification

- `pytest tests/integration/test_custom_docs_endpoints.py -q`
- `pytest tests/test_openapi_contract.py -q`

## Recommended next step

Continue the custom-docs audit in the neighboring runtime docs router:

- `backend/app/api/v1/endpoints/api_documentation.py`

Why:

- `docs.py` is now aligned to the generated contract
- the next obvious stale docs island is the mounted `/api/v1/documentation/*`
  surface, which still contains large hardcoded route narratives and examples
  that predate the current API split
