# W2D Backend Env Example Verification

## Summary

This was a bounded docs-vs-code audit for:

- `backend/.env.example`

The goal was not to expand the template into a full runbook. The goal was to
make the backend env template match the current backend config and the newer
env/setup docs more honestly.

## Findings

### The template still carried stale split Postgres vars

- the old comment block still advertised:
  - `DB_HOST`
  - `DB_PORT`
  - `DB_USER`
  - `DB_PASSWORD`
  - `DB_NAME`
- the active backend config reads `DATABASE_URL`, not those split vars
- the honest fix was to remove that stale comment path and keep a direct
  PostgreSQL `DATABASE_URL` example instead

### The template was missing a few now-important current keys

- current backend config and neighboring setup docs rely on or reference:
  - `FRONTEND_URL`
  - `LOG_LEVEL`
  - `LOG_STRUCTURED`
  - optional backup settings
  - optional FCM settings
- the template was still too narrow for the current docs story, even for a
  bounded dev-first template

### AUTH_SECRET needed to stay out of the backend template on purpose

- the newer ops docs now explicitly call out that `AUTH_SECRET` is compose-side
  legacy residue
- active backend config validates `SECRET_KEY`
- the honest template move was to clarify that `AUTH_SECRET` is intentionally
  absent here rather than silently preserving ambiguity

## What changed

- rewrote `backend/.env.example` as a clearer dev-first backend template
- removed the stale split Postgres env comment block
- added current keys and comments for:
  - `FRONTEND_URL`
  - `LOG_LEVEL`
  - `LOG_STRUCTURED`
  - optional backup settings
  - optional FCM settings
- clarified that the backend template uses `SECRET_KEY`, while legacy
  `AUTH_SECRET` belongs to the ops/compose caveat story, not this template

## Evidence used

- `backend/.env.example`
- `backend/app/core/config.py`
- `backend/env_setup_guide.md`
- `ops/.env.example`

## Verification

- `pytest tests/test_openapi_contract.py -q`

## Recommended next step

Move from docs/templates into a cautious support-file audit:

- `ops/docker-compose.yml`

Likely companion:

- `ops/backend.entrypoint.sh`

Why:

- the env/docs layer is now much more coherent
- the next visible drift sits in the actual compose/runtime support files,
  especially around `AUTH_SECRET`, `ENV=dev`, permissive CORS defaults, and
  backend startup assumptions
