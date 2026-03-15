# Production Setup Summary

Reviewed For Drift: 2026-03-14
Status: companion setup summary with current caveats

## What this file is

This is a shorter companion to:

- `C:/final/backend/SETUP_PRODUCTION.md`

It is no longer a "completed production setup" announcement.

Use it as a quick orientation page, then verify current status in:

- `C:/final/docs/status/AI_FACTORY_OPENHANDS_MASTER_PLAN.md`
- `C:/final/docs/status/OPENHANDS_TASK_BACKLOG.md`
- `C:/final/docs/OPERATOR_STARTUP_COMMANDS.md`

## Current Repo-Backed Assets

- `backend/.env.example`
- `backend/generate_secret_key.py`
- `backend/load_test.py`
- `backend/requirements-monitoring.txt`
- `ops/docker-compose.yml`
- `ops/backend.entrypoint.sh`

## Current Verified Runtime Signals

Published API helpers currently include:

- `GET /api/v1/health`
- `GET /api/v1/status`
- `POST /api/v1/system/backup/create`
- `GET /api/v1/system/backup/list`

Current code-backed verification baseline:

- `pytest tests/test_openapi_contract.py -q` -> `14 passed`
- `pytest -q` -> `850 passed, 3 skipped`

## Current Caveats

- `backend/.env.production` is not committed, even though `ops/docker-compose.yml`
  expects it.
- `ops/docker-compose.yml` still uses `AUTH_SECRET`, while the active app
  config validates `SECRET_KEY`.
- `ops/docker-compose.yml` defaults `ENV=dev` and `CORS_ALLOW_ALL=1`, so it
  should not be treated as a reviewed production-safe default.
- `ops/backend.entrypoint.sh` no longer performs implicit schema bootstrap, so
  schema preparation must happen explicitly before startup.
- `ops/backend.entrypoint.sh` now defaults `ENSURE_ADMIN=0`, so admin
  bootstrap is opt-in instead of implicit.
- `gunicorn` is not present in `backend/requirements.txt`; `uvicorn` is the
  repo-backed runtime dependency.
- monitoring helpers exist, but `monitoring_config.py` is not auto-imported by
  `app/main.py`
- `test_production_readiness.py` is a legacy spot-check, not the canonical
  repo verification gate

## Safer Quick Start

1. Copy `backend/.env.example` to `backend/.env`.
2. Generate and set `SECRET_KEY`.
3. Set `ENV=production`, a production `DATABASE_URL`, strict CORS origins, and
   `FRONTEND_URL`.
4. Run `alembic upgrade head`.
5. Optionally run `python app/scripts/ensure_admin.py` if you intentionally
   want bootstrap admin creation.
   If you intentionally want to mutate an existing matched user, also set
   `ADMIN_ALLOW_UPDATE=1`.
6. Start with `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4`.
7. Verify:
   - `curl http://localhost:8000/api/v1/health`
   - `curl http://localhost:8000/api/v1/status`
   - `pytest tests/test_openapi_contract.py -q`
   - `pytest -q`
8. Run optional helper checks only if needed:
   - `python load_test.py`
   - `python test_production_readiness.py`
   - backup smoke tests
   - optional monitoring helper installation

## Reference Links

- Full setup guide: `C:/final/backend/SETUP_PRODUCTION.md`
- Historical readiness memo: `C:/final/backend/PRODUCTION_READINESS_REPORT.md`
- Current execution SSOT: `C:/final/docs/status/AI_FACTORY_OPENHANDS_MASTER_PLAN.md`
