# W2D Docker Compose Support-File Verification Plan

Scope:

- verify `ops/docker-compose.yml` against the actual repo layout under `ops/`
- allow only a tiny support-file fix if path resolution is provably wrong
- keep auth/default semantics as findings unless a separate approved slice is
  opened

Evidence targets:

- `ops/docker-compose.yml`
- `ops/backend.Dockerfile`
- `ops/frontend.Dockerfile`
- `ops/backend.entrypoint.sh`
- `backend/app/core/config.py`
- `ops/.env.example`
- `docker compose -f C:\final\ops\docker-compose.yml config`

Expected outcome:

- compose path wiring corrected to the repo-root backend/frontend surfaces
- obsolete compose warning noise removed if it is clearly non-behavioral
- the next honest follow-up shifts to a review-first audit of
  `ops/backend.entrypoint.sh`
