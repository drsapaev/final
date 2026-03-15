# W2D Startup Hardening Plan

Status: completed
Branch: `codex/startup-operator-first-hardening`

## Summary

This slice takes the first minimal step from the current convenience-first
startup path toward an operator-first startup model.

Target direction:

- do not keep schema mutation in implicit startup
- do not keep admin mutation enabled by default
- keep explicit operator-controlled admin bootstrap available
- preserve a workable local/dev path without broad infra redesign

## Current Startup Behavior

### Implicit schema bootstrap

`C:/final/ops/backend.entrypoint.sh` currently runs:

- `Base.metadata.create_all(bind=engine)`

before starting Uvicorn.

This means normal startup still performs hidden schema mutation instead of
assuming the schema has already been prepared explicitly.

### Implicit admin bootstrap

`C:/final/ops/backend.entrypoint.sh` currently defaults:

- `ENSURE_ADMIN=1`

and then runs:

- `python app/scripts/ensure_admin.py`

unless explicitly disabled.

### What `ensure_admin.py` can do

`C:/final/backend/app/scripts/ensure_admin.py` is not just “create if missing”.
It can:

- create an admin user
- update an existing user matched by username
- update an existing user matched by email
- normalize role to `Admin`
- reactivate an inactive user
- optionally reset the password via `ADMIN_RESET_PASSWORD`

## Current Controls / Flags

### Entrypoint / bind

- `HOST`
- `PORT`
- `APP_MODULE`
- `WORKERS`
- `RELOAD`

### Database / startup behavior

- `DATABASE_URL`
- `ENSURE_ADMIN`

### Admin bootstrap inputs

- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `ADMIN_EMAIL`
- `ADMIN_FULL_NAME`
- `ADMIN_RESET_PASSWORD`

## Verified Trigger Points

- implicit schema bootstrap trigger:
  - `C:/final/ops/backend.entrypoint.sh`
- explicit migration tool already present:
  - `C:/final/backend/alembic/env.py`
- implicit admin bootstrap trigger:
  - `C:/final/ops/backend.entrypoint.sh`
- explicit admin bootstrap capability:
  - `C:/final/backend/app/scripts/ensure_admin.py`
- startup/deploy docs that currently need operator-first framing:
  - `C:/final/README.md`
  - `C:/final/ops/README.md`
  - `C:/final/backend/SETUP_PRODUCTION.md`
  - `C:/final/backend/PRODUCTION_SETUP_SUMMARY.md`
- env/config examples touching startup/admin semantics:
  - `C:/final/backend/.env.example`
  - `C:/final/ops/.env.example`
  - `C:/final/ops/docker-compose.yml`

## Exact Minimal Change In This Slice

1. Remove implicit `Base.metadata.create_all(...)` from
   `C:/final/ops/backend.entrypoint.sh`.
2. Change admin bootstrap default so startup does not mutate admin state unless
   operators explicitly opt in.
3. Keep the explicit admin bootstrap path available through
   `ENSURE_ADMIN=1` and direct `python app/scripts/ensure_admin.py`.
4. Update startup docs so the expected order is explicit:
   - prepare env
   - prepare/migrate schema
   - optionally ensure admin
   - start app

## Expected Post-Change Startup Contract

### Local/dev

- developers still can run explicit schema preparation
- developers still can opt into admin bootstrap when needed
- app startup itself stops doing hidden schema mutation or default admin
  mutation

### Demo / operator-managed convenience

- admin bootstrap remains available via explicit flag or direct script run
- schema preparation remains an explicit operator step

### Production / operator-first

- run migrations explicitly
- optionally run `ensure_admin.py` explicitly
- then start the app

## Out Of Scope

- no broad deployment redesign
- no Alembic workflow rewrite
- no auth/user model refactor
- no Docker/compose architecture rewrite
- no full local/dev wrapper redesign
- no guarantee that every historical helper script becomes operator-grade in
  this slice

## Validation Plan

- validate `C:/final/ops/backend.entrypoint.sh` syntax/references
- run:
  - `cd C:\final\backend && pytest tests/test_openapi_contract.py -q`
- run any narrow startup/bootstrap-adjacent checks only if they already exist
  and remain relevant
