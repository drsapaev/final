# W2D Operator-First Startup

## Summary

This slice moves the repo from implicit startup mutation toward an
operator-first startup model with a small, pragmatic step:

- no implicit schema bootstrap during app startup
- no default admin bootstrap during app startup
- explicit admin bootstrap remains available
- local/dev and demo flows stay usable through explicit, short commands

This is the first bounded step toward operator-first startup, not a broad
deployment redesign.

## What Changed

### Implicit schema bootstrap removed

`C:/final/ops/backend.entrypoint.sh` no longer runs:

- `Base.metadata.create_all(bind=engine)`

Startup now assumes schema preparation already happened explicitly.

### Admin bootstrap is now opt-in

`C:/final/ops/backend.entrypoint.sh` now defaults:

- `ENSURE_ADMIN=0`

Admin bootstrap only runs when operators explicitly opt in with
`ENSURE_ADMIN=1`, or when they run:

- `python app/scripts/ensure_admin.py`

directly.

## Startup Flows

### Local / Dev Convenience Path

Recommended flow:

1. copy env from `backend/.env.example`
2. prepare schema explicitly
   - `cd backend && alembic upgrade head`
3. optionally bootstrap admin explicitly
   - `cd backend && python app/scripts/ensure_admin.py`
4. start the app
   - `cd backend && uvicorn app.main:app --reload`

What changed:

- the app no longer creates tables automatically on startup
- the app no longer mutates admin state by default on startup

### Demo / Compose Path

Recommended flow:

1. review compose/runtime env values
2. prepare schema explicitly
   - `cd ops && docker compose run --rm backend alembic upgrade head`
3. optionally bootstrap admin explicitly
   - `cd ops && docker compose run --rm backend python app/scripts/ensure_admin.py`
4. start the stack
   - `cd ops && docker compose up --build`

### Production / Operator Path

Recommended flow:

1. prepare reviewed runtime env
2. run schema migration explicitly
   - `cd backend && alembic upgrade head`
3. optionally run explicit admin bootstrap
   - `cd backend && python app/scripts/ensure_admin.py`
4. start the app/service
5. run live verification

## Why This Is Safer

- startup is no longer allowed to hide schema mutation
- startup is no longer allowed to mutate admin state unless operators
  intentionally request it
- migrations remain the explicit schema path already used elsewhere in the repo
- the remaining admin helper is now clearly a tool, not a silent startup side
  effect

## What Remains Out Of Scope

- no Alembic workflow redesign
- no deployment-system rewrite
- no auth/user model refactor
- no ensure-admin behavior rewrite in this slice
- no dev/demo wrapper tooling added in this slice

## Current Verdict

The startup model is now sufficiently operator-first for this bounded step:

- hidden startup mutation is removed
- explicit operator bootstrap paths remain available

The main remaining startup-adjacent tail is no longer implicit startup itself,
but the behavior contract of `ensure_admin.py`.
