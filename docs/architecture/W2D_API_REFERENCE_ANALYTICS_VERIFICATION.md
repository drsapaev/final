# W2D API Reference Analytics Verification

## Summary

This was a bounded docs-vs-code verification pass for `docs/API_REFERENCE.md`.

The goal was not to fully re-document the entire analytics subsystem. The goal
was to correct high-confidence drift in the `Analytics` section while keeping
the slice docs-only.

## Findings

### Analytics section was still advertising removed top-level routes

- the doc still advertised:
  - `GET /analytics/overview`
  - `GET /analytics/payment-providers`
  - `GET /analytics/appointment-flow`
  - `GET /analytics/revenue-breakdown`
- those routes are not present in the current published OpenAPI
- the live core analytics owner now exposes:
  - `GET /api/v1/analytics/quick-stats`
  - `GET /api/v1/analytics/dashboard`
  - `GET /api/v1/analytics/trends`

### Current analytics surface is much broader than the old summary

- adjacent authenticated analytics families now live under:
  - `/api/v1/analytics/advanced/*`
  - `/api/v1/analytics/kpi-*`
  - `/api/v1/analytics/predictive/*`
  - `/api/v1/analytics/export/*`
  - `/api/v1/analytics/visualization/*`
  - `/api/v1/analytics/ai/*`
  - `/api/v1/analytics/wait-time/*`
- explicit public health exceptions exist at:
  - `/api/v1/analytics/advanced/health`
  - `/api/v1/analytics/export/health`
  - `/api/v1/analytics/visualization/health`

### Access notes are now more nuanced than the old section implied

- the live core dashboard routes in `analytics.py` currently check the role set
  `admin`, `doctor`, `nurse`
- many adjacent analytics families are authenticated but use different
  dependencies or more specific role gates
- the old section did not distinguish between these surfaces at all

### Most analytics response shapes are intentionally broad in generated schema

- many analytics routes publish `{}` or free-form objects in
  `backend/openapi.json`
- the honest docs move was to document route families and access notes rather
  than inventing exact payload contracts for routes that are still loosely
  typed

## What changed

- updated the `Analytics` section in `docs/API_REFERENCE.md` to a curated
  modern analytics map
- replaced removed top-level routes with the live core dashboard routes
- added the adjacent analytics families and the explicit public health routes
- downgraded exact response claims where generated schema is intentionally broad

## Evidence used

- `backend/openapi.json`
- `backend/app/api/v1/endpoints/analytics.py`
- `backend/app/api/v1/endpoints/advanced_analytics.py`
- `backend/app/api/v1/endpoints/ai_analytics.py`
- `backend/app/api/v1/endpoints/wait_time_analytics.py`

## Recommended next step

Continue the broader `API_REFERENCE.md` verification track with another bounded
slice rather than a full rewrite.

Good next candidates:

- `Departments`
- `Services`
