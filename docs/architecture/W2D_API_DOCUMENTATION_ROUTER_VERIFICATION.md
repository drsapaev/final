# W2D API Documentation Router Verification

## Summary

This was a bounded docs-vs-code audit for the mounted runtime docs router in
`backend/app/api/v1/endpoints/api_documentation.py`.

The goal was to stop this helper router from serving a second hand-written API
spec that had drifted away from the live application.

## Findings

### The custom `/api/v1/documentation/*` router had become a stale mini-spec

- `GET /api/v1/documentation/documentation/endpoints` returned hardcoded
  categories and route stories from an older API shape
- `GET /api/v1/documentation/documentation/examples` still advertised old visit
  and other request examples
- `GET /api/v1/documentation/documentation/status-codes` used a generic static
  table instead of current repo-specific response patterns
- `GET /api/v1/documentation/documentation/authentication` still documented old
  auth assumptions such as `Nurse`, fixed token-expiration text, and a tiny
  simplified role map

### There were no live code or frontend consumers for these helper routes

- a focused search across `backend/app`, `backend/tests`, `frontend/src`, and
  `docs` found no live consumers for the `/api/v1/documentation/*` routes
- this made it safe to change the helper response shapes as long as the routes
  themselves remained mounted

## What changed

- replaced the hardcoded endpoint catalog with a generated category index based
  on the current OpenAPI schema
- replaced the old examples payload with a smaller curated live-examples helper
  using current route families such as `/api/v1/auth/minimal-login`,
  `/api/v1/patients/`, `/api/v1/visits/visits`, and the modern queue join flow
- replaced the static status-code table with a generated common-code guide
  derived from the current schema
- replaced the static auth guide with a generated helper that exposes the live
  `OAuth2PasswordBearer` scheme, current token URLs, and current auth-adjacent
  route families
- added dedicated integration coverage for the helper router

## Evidence used

- `backend/app/api/v1/endpoints/api_documentation.py`
- `backend/app/api/v1/api.py`
- `backend/app/main.py`
- `backend/openapi.json`
- focused code/docs search for `/api/v1/documentation/*` consumers across:
  - `backend/app`
  - `backend/tests`
  - `frontend/src`
  - `docs`

## Verification

- `pytest tests/integration/test_api_documentation_helpers.py -q`
- `pytest tests/test_openapi_contract.py -q`
- `pytest -q`

## Recommended next step

The runtime custom-docs surfaces are now largely aligned.

The next honest low-risk docs-vs-code candidate is:

- `backend/PRODUCTION_READINESS_REPORT.md`

Why:

- it still presents an old point-in-time readiness verdict
- it is a broad status/report document, not a generated contract source
- it is a better next stale-doc audit target than continuing to invent more
  custom runtime API documentation
