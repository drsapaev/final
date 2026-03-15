# W2D Ops README and Env Verification

## Summary

This was a bounded docs-vs-code audit for:

- `ops/README.md`
- `ops/.env.example`

The goal was not to redesign the compose stack. The goal was to stop the ops
entrypoint docs from reading like a clean turnkey deployment story where the
current compose/env wiring still contains visible local/dev and legacy-auth
assumptions.

## Findings

### The ops README mixed local/dev assumptions with production-sounding language

- it still described SQLite as the default database story
- it still presented `AUTH_SECRET` as the JWT secret
- it still implied `CORS_ALLOW_ALL=1` and the admin bootstrap defaults as
  normal quick-start guidance
- but the current compose file defaults to PostgreSQL, keeps `ENV=dev`,
  defaults `CORS_ALLOW_ALL=1`, and still expects `backend/.env.production`
  separately

### The current env example needed clearer scope

- `ops/.env.example` looked like a general runtime env file
- but the current compose stack distinguishes:
  - compose interpolation variables
  - backend runtime env via `backend/.env.production`
- without stronger framing, readers could mistake the example for the only env
  file they need

### AUTH_SECRET is now legacy residue relative to active backend config

- the compose file still interpolates `AUTH_SECRET`
- the active backend settings validate `SECRET_KEY`
- the honest docs move was to keep that mismatch visible instead of pretending
  the ops env layer is already fully aligned

## What changed

- rewrote `ops/README.md` into a clearer compose-oriented ops note with current
  caveats
- separated compose interpolation from backend runtime env responsibilities
- corrected the README away from SQLite-default wording and toward the current
  PostgreSQL-first compose story
- reframed admin bootstrap and permissive CORS as local/dev conveniences, not
  production defaults
- updated `ops/.env.example` comments so it now explains:
  - it does not replace `backend/.env.production`
  - `SECRET_KEY` is the active backend secret
  - `AUTH_SECRET` remains legacy compose residue

## Evidence used

- `ops/README.md`
- `ops/.env.example`
- `ops/docker-compose.yml`
- `ops/backend.entrypoint.sh`
- `backend/app/core/config.py`
- `backend/app/scripts/ensure_admin.py`

## Verification

- `pytest tests/test_openapi_contract.py -q`

## Recommended next step

Continue the neighboring env-docs audit with:

- `backend/env_setup_guide.md`

Why:

- after the backend production docs and ops entrypoint docs are normalized, the
  next visible env-facing doc still carrying older setup assumptions is the
  backend environment guide
