# W2D Docker Compose Support-File Verification Status

Status: completed

What changed:

- `ops/docker-compose.yml` no longer uses repo-root-style relative paths from
  inside `ops/`
- backend/frontend build contexts now point at `..`
- backend runtime `env_file` now points at `../backend/.env.production`
- backend/frontend bind mounts now point at `../backend` and `../frontend`
- the obsolete compose `version` stanza was removed

Validation:

- `docker compose -f C:\final\ops\docker-compose.yml config`
  - now resolves the missing runtime env file to
    `C:\final\backend\.env.production`
  - the previous wrong path `C:\final\ops\backend\.env.production` is gone
- `pytest tests/test_openapi_contract.py -q` -> `14 passed`

Result:

- the compose file now points at the intended repo-backed backend/frontend
  surfaces instead of a broken `ops/`-relative pseudo-layout
- behavior-bearing auth/dev defaults remain explicitly unresolved in this slice
- the next low-risk support-file follow-up shifts to
  `ops/backend.entrypoint.sh`
