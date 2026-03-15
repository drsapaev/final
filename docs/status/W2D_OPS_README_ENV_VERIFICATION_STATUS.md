# W2D Ops README and Env Verification Status

Status: completed

What changed:

- `ops/README.md` now reads as a compose-oriented ops note with current caveats
  instead of a simple deployment recipe
- `ops/.env.example` now explicitly says it does not replace
  `backend/.env.production`
- the docs now distinguish:
  - PostgreSQL-first compose defaults
  - local/dev conveniences such as permissive CORS and default admin bootstrap
  - legacy `AUTH_SECRET` compose wiring versus active `SECRET_KEY` backend
    validation

Validation:

- `pytest tests/test_openapi_contract.py -q` -> `14 passed`
- ops/env claims were checked against:
  - `ops/docker-compose.yml`
  - `ops/backend.entrypoint.sh`
  - `backend/app/core/config.py`
  - `backend/app/scripts/ensure_admin.py`

Result:

- the ops-facing entry docs no longer hide the current env/compose caveats
- the next low-risk env-docs target has shifted to `backend/env_setup_guide.md`
