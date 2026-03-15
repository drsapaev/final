# W2D Docker Compose Support-File Verification

## Summary

This was a bounded review-first support-file audit for:

- `ops/docker-compose.yml`

The goal was not to redesign deployment defaults or rewrite the ops stack.
The goal was to verify whether the current compose file still pointed at the
real repo layout from inside `ops/`, and to apply only the smallest proven
support-file fix.

## Findings

### Compose path resolution was broken from inside `ops/`

- `docker compose -f C:\final\ops\docker-compose.yml config` resolved
  `env_file` to `C:\final\ops\backend\.env.production`
- the repo-backed runtime env location is `C:\final\backend\.env.production`
- that proved the compose file was still carrying root-style relative paths
  even though the file itself lives under `ops/`

### The same drift affected build contexts and bind mounts

- backend and frontend both used `context: .`
- backend and frontend both bind-mounted `./backend` or `./frontend`
- but the Dockerfiles and repo layout assume the repo root as build context,
  not `C:\final\ops\`
- without correcting those paths, the compose file could not honestly be
  treated as pointing at the intended repo-backed surfaces

### The obsolete `version` stanza added warning noise

- current Docker Compose warned that `version` is obsolete and ignored
- removing it was a safe clarity fix inside the same bounded slice

### Auth and local/dev defaults remain a separate support-file tail

- compose still interpolates `AUTH_SECRET`
- compose still defaults `ENV=dev`, `CORS_ALLOW_ALL=1`, and local bootstrap
  credentials
- those are behavior-bearing defaults and did not belong in this path-wiring
  fix

## What changed

- removed the obsolete top-level `version` stanza from
  `ops/docker-compose.yml`
- changed backend and frontend build contexts from `.` to `..`
- kept Dockerfile paths aligned to repo root:
  - `ops/backend.Dockerfile`
  - `ops/frontend.Dockerfile`
- changed backend `env_file` to `../backend/.env.production`
- changed bind mounts to:
  - `../backend:/app:rw`
  - `../frontend:/app:rw`
- added a short inline note that compose paths are resolved relative to
  `ops/docker-compose.yml`

## Evidence used

- `ops/docker-compose.yml`
- `ops/backend.Dockerfile`
- `ops/frontend.Dockerfile`
- `ops/backend.entrypoint.sh`
- `backend/app/core/config.py`
- `ops/.env.example`
- `docker compose -f C:\final\ops\docker-compose.yml config`

## Verification

- `docker compose -f C:\final\ops\docker-compose.yml config`
  - now fails on the honest missing file
    `C:\final\backend\.env.production`
  - it no longer fails on the previously wrong path
    `C:\final\ops\backend\.env.production`
- `pytest tests/test_openapi_contract.py -q`
  - `14 passed`

## Recommended next step

Continue the same support-file audit lane with:

- `ops/backend.entrypoint.sh`

Likely companions:

- `backend/app/main.py`
- `backend/app/scripts/ensure_admin.py`

Why:

- compose path wiring is now aligned to the real repo layout
- the remaining visible ops drift sits in startup assumptions:
  - metadata `create_all` versus migration-first expectations
  - optional admin bootstrap behavior
  - `/data`-side SQLite fallback/defaults
  - how those assumptions match the newer production-facing docs
