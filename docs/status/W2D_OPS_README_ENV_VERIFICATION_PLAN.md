# W2D Ops README and Env Verification Plan

Scope:

- verify `ops/README.md` against the current compose file, backend config, and
  entrypoint behavior
- verify the coupled support file `ops/.env.example` in the same bounded slice
- keep the work docs/support-file only, with no compose/runtime changes

Evidence targets:

- `ops/docker-compose.yml`
- `ops/backend.entrypoint.sh`
- `backend/app/core/config.py`
- `backend/app/scripts/ensure_admin.py`
- `ops/README.md`
- `ops/.env.example`

Expected outcome:

- ops docs stop presenting a turnkey production story
- compose interpolation and backend runtime env responsibilities are separated
- legacy `AUTH_SECRET` drift is called out honestly instead of hidden
- the next low-risk target shifts to `backend/env_setup_guide.md`
