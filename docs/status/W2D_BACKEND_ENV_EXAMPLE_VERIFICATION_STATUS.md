# W2D Backend Env Example Verification Status

Status: completed

What changed:

- `backend/.env.example` now reads as a clearer dev-first backend template
- stale split Postgres `DB_HOST/DB_PORT/...` comments were removed
- the template now includes current guide-level support for:
  - `FRONTEND_URL`
  - `LOG_LEVEL`
  - `LOG_STRUCTURED`
  - optional backup settings
  - optional FCM settings
- the template now explicitly stays on the `SECRET_KEY` path and does not
  pretend that legacy `AUTH_SECRET` belongs in backend runtime config

Validation:

- `pytest tests/test_openapi_contract.py -q` -> `14 passed`
- template claims were checked against:
  - `backend/app/core/config.py`
  - `backend/env_setup_guide.md`
  - `ops/.env.example`

Result:

- the backend template no longer competes with current config as a stale partial
  env contract
- the next low-risk step shifts from docs/templates to a cautious
  support-file audit of `ops/docker-compose.yml`
