# W2D API Reference Health Auth Header Verification

## Summary

This was a bounded docs-vs-code verification pass for `docs/API_REFERENCE.md`.

The goal was not to fully re-document every footer/meta section. The goal was
to correct high-confidence drift in the `Health` and `Authentication Header`
sections while keeping the slice docs-only.

## Findings

### Health section was still mixing API-scoped and non-API-scoped root claims

- the doc still advertised:
  - `GET /`
  - `GET /health`
- the file’s own base URL is `/api/v1`, so the root `/` claim was stale in this
  context
- the live mounted health owner currently publishes:
  - `GET /api/v1/health`
  - `GET /api/v1/status`

### Health surface is now broader than one generic endpoint

- current published health-style routes also exist across adjacent subsystems,
  including:
  - `/api/v1/authentication/health`
  - `/api/v1/analytics/advanced/health`
  - `/api/v1/analytics/export/health`
  - `/api/v1/analytics/visualization/health`
  - `/api/v1/mobile/health`
  - `/api/v1/2fa/health`
  - `/api/v1/system/monitoring/health`
  - `/api/v1/ai/v2/health`
  - `/api/v1/mcp/health`
- some of those are public and some are authenticated
- the honest docs move was to keep the section curated and call out the split
  instead of pretending one route represents all health behavior

### Authentication Header section was too generic for the current published scheme

- the old section only said:
  - `Authorization: Bearer <access_token>`
- current published OpenAPI exposes a named security scheme:
  - `OAuth2PasswordBearer`
  - password flow
  - `tokenUrl: /api/v1/auth/minimal-login`
- that specific scheme information was missing from the docs

### “All protected endpoints require” needed a public-route caveat

- current published OpenAPI still includes many public routes
- examples include:
  - `/api/v1/health`
  - several subsystem health endpoints
  - public payment/provider/webhook routes
  - public queue lookup/join routes
- the honest docs move was to scope the header guidance to routes that actually
  declare the published auth scheme

## What changed

- updated the `Health` section in `docs/API_REFERENCE.md` to the live
  `/health` plus `/status` owner shape
- removed the stale root `/` claim from the API-scoped reference
- added a curated split between public and authenticated adjacent health routes
- updated the `Authentication Header` section to the current published
  `OAuth2PasswordBearer` scheme and password-flow token URL
- added a caveat that not every route in the API reference is protected

## Evidence used

- `backend/openapi.json`
- `backend/app/api/v1/api.py`
- `backend/app/api/v1/endpoints/health.py`

## Recommended next step

Continue the broader `API_REFERENCE.md` verification track with another bounded
slice rather than a full rewrite.

Good next candidates:

- `HTTP Status Codes`
- `Roles & Permissions`
