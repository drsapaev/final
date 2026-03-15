# Ops / Deployment

Reviewed For Drift: 2026-03-14
Status: compose-oriented ops note with current caveats

## How to use this file

This file is not a production approval memo.

Use it as a short orientation page for the current Docker/ops surface, then
confirm current execution status in:

- `C:/final/docs/status/AI_FACTORY_OPENHANDS_MASTER_PLAN.md`
- `C:/final/docs/status/OPENHANDS_TASK_BACKLOG.md`

## What currently exists

Repo-backed ops files:

- `ops/docker-compose.yml`
- `ops/backend.Dockerfile`
- `ops/backend.entrypoint.sh`
- `ops/frontend.Dockerfile`
- `ops/.env.example`

Current compose services:

- backend
- frontend
- postgres

Published app endpoints still point to:

- Backend docs: `http://localhost:8000/docs`
- Backend OpenAPI: `http://localhost:8000/openapi.json`
- Frontend dev server: `http://localhost:5173`

## Current Caveats

- `ops/docker-compose.yml` expects `backend/.env.production`, but that file is
  not committed in the repo.
- The current compose defaults lean local/dev unless reviewed:
  - `ENV=dev`
  - `CORS_ALLOW_ALL=1`
  - `ADMIN_PASSWORD=admin`
- Compose still interpolates `AUTH_SECRET`, but the active backend settings
  validate `SECRET_KEY`.
- `ops/backend.entrypoint.sh` no longer creates tables or bootstraps admin by
  default; operators now need explicit schema preparation and explicit
  `ENSURE_ADMIN=1` or direct `ensure_admin.py` usage if they want bootstrap
  behavior.
- Treat the current compose stack as a review-required ops surface, not as a
  turnkey production recipe.

## Env Files and Responsibilities

There are two different env layers in this ops story:

### 1. Compose interpolation example

- `ops/.env.example`

Use this as a reference for values that `ops/docker-compose.yml` interpolates.

### 2. Backend runtime env file

- `backend/.env.production`

The current compose file explicitly expects this file via `env_file`, so
`ops/.env.example` does not replace it.

## Compose-Oriented Quick Start

Canonical commands now live in:

- `C:/final/docs/OPERATOR_STARTUP_COMMANDS.md`

All command examples below assume repository-root execution.

If you are using the current compose stack, review these items before startup:

- `DATABASE_URL`
- `SECRET_KEY` in `backend/.env.production`
- legacy `AUTH_SECRET` interpolation in compose
- `ENV`
- `CORS_ALLOW_ALL`
- `ENSURE_ADMIN`
- admin bootstrap credentials

Then follow the explicit startup flow:

1. prepare schema explicitly
   - for example:
     `docker compose -f ops/docker-compose.yml run --rm backend alembic upgrade head`
2. optionally bootstrap admin explicitly
   - for example:
     `docker compose -f ops/docker-compose.yml run --rm backend python app/scripts/ensure_admin.py`
3. start the stack
   - `docker compose -f ops/docker-compose.yml up --build`

## Current Service Notes

### Backend

- startup path is `uvicorn` via `ops/backend.entrypoint.sh`
- current default bind is `0.0.0.0:8000`
- container startup now assumes schema was prepared explicitly
- admin bootstrap only runs when `ENSURE_ADMIN=1`

### Frontend

- current container exposes Vite dev server on port `5173`
- `VITE_API_BASE` defaults to `http://localhost:8000/api/v1`

### Postgres

- current compose defaults target PostgreSQL, not SQLite
- persistent database data goes to `postgres_data`

### Backend Data Volume

- `backend_data` remains mounted to `/data`
- if you intentionally override to a SQLite path under `/data`, that volume can
  still hold app-side artifacts

## Admin Bootstrap

`backend/app/scripts/ensure_admin.py` still exists, but bootstrap is now an
explicit operator action.

Important caveat:

- `ENSURE_ADMIN=0` is now the default
- the script defaults to `admin/admin` if you do not override the env vars
- that is a local/dev convenience, not a production-safe default

If you intentionally want bootstrap, either:

- run:
  `docker compose -f ops/docker-compose.yml run --rm backend python app/scripts/ensure_admin.py`
- or set `ENSURE_ADMIN=1` for the startup that should perform bootstrap

If you intentionally want to mutate an existing matched user
(promote/reactivate/rename/update profile fields), also set:

- `ADMIN_ALLOW_UPDATE=1`

Review these variables before using bootstrap in a serious environment:

- `ENSURE_ADMIN`
- `ADMIN_ALLOW_UPDATE`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `ADMIN_EMAIL`
- `ADMIN_FULL_NAME`
- `ADMIN_RESET_PASSWORD`

## Production Reader Note

For a production-style deployment story, also review:

- `C:/final/backend/SETUP_PRODUCTION.md`
- `C:/final/backend/PRODUCTION_SETUP_SUMMARY.md`
- `C:/final/backend/PRODUCTION_READINESS_REPORT.md`
- `C:/final/backend/PRODUCTION_READINESS_CHECKLIST.md`

## Next Neighboring Doc

The next low-risk env/docs follow-up after this ops note is:

- `backend/env_setup_guide.md`
