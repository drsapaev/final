# W2D Backend Entrypoint Support-File Verification

## Summary

This was a bounded review-first support-file audit for:

- `ops/backend.entrypoint.sh`

The goal was not to redesign container startup. The goal was to verify whether
the current entrypoint still aligned with the active backend config/env story,
and to apply only the smallest proven fix.

## Findings

### The entrypoint silently overrode the current backend SQLite fallback

- the script defaulted `DATABASE_URL` to `sqlite:////data/app.db`
- current backend config falls back to `sqlite:///./clinic.db`
- the current backend env template also defaults to `sqlite:///./clinic.db`
- the current ops docs already describe `/data` as an intentional override
  path, not as the normal silent fallback

That made the entrypoint the outlier in the current env/config/docs stack.

### `/data` remains useful, but it should not be the hidden default

- the compose stack still mounts `backend_data` to `/data`
- keeping `/data` available is still useful for explicit SQLite overrides or
  app-side artifacts
- but forcing `/data/app.db` as the startup default made the support file
  disagree with the newer backend template and config ownership

### `create_all` and auto-admin remain behavior-bearing startup tails

- the entrypoint still runs `Base.metadata.create_all(...)`
- the entrypoint still optionally runs `backend/app/scripts/ensure_admin.py`
- those behaviors are real startup semantics, not just path/config drift
- they were left untouched in this slice and should be treated as a separate
  review/decision surface

## What changed

- changed the entrypoint fallback from:
  - `sqlite:////data/app.db`
- to:
  - `sqlite:///./clinic.db`
- added an inline note explaining that:
  - the fallback is intentionally aligned with backend config/env templates
  - `/data` remains available for explicit overrides, not as the silent default
- updated the nearby comment in `ops/.env.example` so `/data/app.db` now reads
  as an explicit SQLite override example instead of an implied default

## Evidence used

- `ops/backend.entrypoint.sh`
- `backend/app/core/config.py`
- `backend/app/db/session.py`
- `backend/.env.example`
- `ops/.env.example`
- `ops/README.md`
- `backend/SETUP_PRODUCTION.md`
- `backend/PRODUCTION_SETUP_SUMMARY.md`

## Verification

- `pytest tests/test_openapi_contract.py -q`
  - `14 passed`

## Recommended next step

Do not continue with another silent startup edit.

Open a plan-gated review for the remaining behavior-bearing entrypoint tails:

- `Base.metadata.create_all(...)`
- `ENSURE_ADMIN` / `backend/app/scripts/ensure_admin.py`

Likely companions:

- `backend/app/main.py`
- `backend/app/scripts/ensure_admin.py`
- `ops/README.md`
- `backend/SETUP_PRODUCTION.md`

Why:

- the path/config drift is now resolved
- the remaining startup differences are about deployment semantics and operator
  expectations, not just string/path alignment
